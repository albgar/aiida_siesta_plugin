from aiida import orm
from aiida.common.exceptions import NotExistent
from aiida.engine import WorkChain, calcfunction, ToContext
from aiida.common import AttributeDict
from aiida.tools import get_explicit_kpoints_path
from aiida_siesta.calculations.siesta import internal_structure
from aiida_siesta.workflows.base import SiestaBaseWorkChain
from aiida_siesta.utils.tkdict import FDFDict


def drop_md_keys(param):
    for item in param.copy().keys():
        trans_item = FDFDict.translate_key(item)
        if trans_item.startswith("md"):
            param.pop(item)
    return param


@calcfunction
def get_bandgap(e_fermi, band):
    """
    Takes a band object, and a Fermi energy, and extracts the band gap value and 'is_insulator' boolean
    :param band: (orm.BandsData): band-structure object
    :param e_energy: (orm.Float): value of the fermi energy.
    :return: An orm.Dict containing the keys:
        'band_gap': A float, or None in case of a metal. It is zero when the homo is
                          equal to the lumo (e.g. in semi-metals).
        'band_gap_units': A string, here 'eV'
        'is_insulator': A boolean
    """
    from aiida.orm.nodes.data.array.bands import find_bandgap

    is_insulator, bandgap = find_bandgap(fermi_energy=e_fermi.value, bandsdata=band)
    output = {}
    output['band_gap'] = bandgap
    output['band_gap_units'] = 'eV'
    output['is_insulator'] = is_insulator
    return orm.Dict(dict=output)


def validate_inputs(value, _):
    """
    Validate the entire input namespace. It takes care to ckeck the consistency
    and compatibility of the inputed basis, pseudos, pseudofamilies and ions.
    It is the same validator of the SiestaBaseWorkChain but with no warnings on bandkpoints.
    """
    import warnings

    if 'basis' in value:
        structure = internal_structure(value["structure"], value["basis"].get_dict())
        if structure is None:
            return "Not possibe to specify `floating_sites` (ghosts) with the same name of a structure kind."
    else:
        structure = value["structure"]

    #Check each kind in the structure (including freshly added ghosts) have a corresponding pseudo or ion
    kinds = [kind.name for kind in structure.kinds]
    if 'ions' in value:
        quantity = 'ions'
        if 'pseudos' in value or 'pseudo_family' in value:
            warnings.warn("At least one ion file in input, all the pseudos or pseudo_family will be ignored")
    else:
        quantity = 'pseudos'
        if 'pseudos' not in value and 'pseudo_family' not in value:
            return "No `pseudos`, nor `ions`, nor `pseudo_family` specified in input"
        if 'pseudos' in value and 'pseudo_family' in value:
            return "You cannot specify both `pseudos` and `pseudo_family`"

    if 'pseudo_family' in value:
        group = orm.Group.get(label=value['pseudo_family'].value)
        # To be removed in v2.0
        if "data" in group.type_string:
            from aiida_siesta.data.common import get_pseudos_from_structure
            try:
                get_pseudos_from_structure(structure, value['pseudo_family'].value)
            except NotExistent:
                return "The pseudo family does not incude all the required pseudos"
        else:
            try:
                group.get_pseudos(structure=structure)
            except ValueError:
                return "The pseudo family does not incude all the required pseudos"
    else:
        if set(kinds) != set(value[quantity].keys()):
            ps_io = ', '.join(list(value[quantity].keys()))
            kin = ', '.join(list(kinds))
            string_out = (
                'mismatch between defined pseudos/ions and the list of kinds of the structure\n' +
                f' pseudos/ions: {ps_io} \n kinds(including ghosts): {kin}'
            )
            return string_out


class BandgapWorkChain(WorkChain):
    """
    Workchain to obtain the bands and bandgap of a structure through Siesta.
    If "bandskpoints" are set in inputs, it behaves like `SiestaBaseWorkChain`
    adding just the bandgap calculation at the end. If no bandskpoints
    was specified, the bands are computed anyway on a kpoints path automatically
    assigned using seekpath and the input (output) structure
    of the single-point (relaxation/md) calculation.
    """

    @classmethod
    def define(cls, spec):
        super().define(spec)
        spec.expose_inputs(SiestaBaseWorkChain, exclude=('metadata',))
        spec.expose_outputs(SiestaBaseWorkChain)
        spec.input(
            'seekpath_dict',
            valid_type=orm.Dict,
            default=lambda: orm.Dict(dict={
                'reference_distance': 0.02,
                'symprec': 0.0001
            }),
            help='dictionary of seekpath parameters that are pased to `get_explicit_kpoints_path`'
        )
        spec.output('band_gap_info', valid_type=orm.Dict, required=False)
        spec.outline(
            cls.preprocess,
            cls.run_siesta_wc,
            cls.run_last,
            cls.run_results,
        )
        spec.inputs.validator = validate_inputs
        spec.exit_code(200, 'ERROR_MAIN_WC', message='The main SiestaBaseWorkChain failed')
        spec.exit_code(201, 'ERROR_FINAL_WC', message='The SiestaBaseWorkChain to obtain the bands failed')

    def preprocess(self):
        """
        In the preprocess, we make decisions on bandskpoints if they are not requested in input.
        In case of single point calculation, bandskpoints are added using seekpath.
        In case of relaxation, the relaxation is run, but an extra step at the end of
        the calculation will calculate the bands.
        """
        self.ctx.need_fin_step = False
        var_geom = False
        self.ctx.need_to_generate_bandskp = False

        #The relaxation in Siesta is triggered by md-steps keyword.
        #I verified taht md-type of run alone do not trigger veriable geometry.
        fdf_par = FDFDict(self.inputs.parameters.get_dict())
        for item in fdf_par:
            if item in [FDFDict.translate_key("mdsteps"), FDFDict.translate_key("mdnumcgsteps")]:
                if fdf_par[item] != 0:
                    var_geom = True
                    break

        if "bandskpoints" not in self.inputs:
            if var_geom:
                self.report(
                    "The kpoints path for the calculation of bands will be automatically generated "
                    "using seekpath. Because a relaxation was requested, the bands calculation will "
                    "be performed on a separate final step. The cell of the final step might change "
                    "due to seekpath. This cell is returned in `output_structure`."
                )
                self.ctx.need_fin_step = True
            else:
                self.report(
                    "The kpoints path for the calculation of bands will be automatically generated "
                    "using seekpath. Because of seekpath, the cell might change."
                )
                self.ctx.need_to_generate_bandskp = True

    def run_siesta_wc(self):
        """
        Run the SiestaBaseWorkChain, might be a relaxation or a scf only.
        """

        self.report('Initial checks where succesfull')

        inputs = AttributeDict(self.exposed_inputs(SiestaBaseWorkChain))

        if self.ctx.need_to_generate_bandskp:
            seekpath_parameters = self.inputs.seekpath_dict.get_dict()
            result = get_explicit_kpoints_path(inputs["structure"], **seekpath_parameters)
            inputs["structure"] = result['primitive_structure']
            inputs["bandskpoints"] = result['explicit_kpoints']
            self.report("Added bandskpoints to the calculation using seekpath")

        running = self.submit(SiestaBaseWorkChain, **inputs)
        self.report(f'Launched SiestaBaseWorkChain<{running.pk}> to perform the siesta calculation.')

        return ToContext(workchain_base=running)

    def run_last(self):
        """
        Only post process is the calculation of the band gap from the band, knowing the fermi energy.
        """
        if not self.ctx.workchain_base.is_finished_ok:
            return self.exit_codes.ERROR_MAIN_WC

        if self.ctx.need_fin_step:
            seekpath_parameters = self.inputs.seekpath_dict.get_dict()
            out_structure = self.ctx.workchain_base.outputs.output_structure
            result = get_explicit_kpoints_path(out_structure, **seekpath_parameters)
            new_calc = self.ctx.workchain_base.get_builder_restart()
            new_calc.structure = result['primitive_structure']
            new_calc.bandskpoints = result['explicit_kpoints']
            new_param = drop_md_keys(new_calc.parameters.get_dict())
            new_calc.parameters = orm.Dict(dict=new_param)
            running = self.submit(new_calc)
            self.report(f'Launched SiestaBaseWorkChain<{running.pk}> to calculate bands.')
            return ToContext(final_run=running)

    def run_results(self):
        if self.ctx.need_fin_step:
            if not self.ctx.final_run.is_finished_ok:
                return self.exit_codes.ERROR_FINAL_WC
            outps = self.ctx.final_run.outputs
            self.out('output_structure', self.ctx.final_run.inputs.structure)
        else:
            outps = self.ctx.workchain_base.outputs

        if 'forces_and_stress' in outps:
            self.out('forces_and_stress', outps['forces_and_stress'])
        self.out('bands', outps['bands'])
        self.out('output_parameters', outps['output_parameters'])
        self.out('remote_folder', outps['remote_folder'])

        self.report("Obtaining the band gap")
        out_par = outps['output_parameters']
        e_fermi = out_par.get_dict()['E_Fermi']
        res_dict = get_bandgap(orm.Float(e_fermi), outps["bands"])
        self.out('band_gap_info', res_dict)

    @classmethod
    def inputs_generator(cls):  # pylint: disable=no-self-argument,no-self-use
        from aiida_siesta.utils.protocols_system.input_generators import BaseWorkChainInputGenerator
        return BaseWorkChainInputGenerator(cls)
