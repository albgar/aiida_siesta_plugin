#!/usr/bin/env runaiida
import pytest
from plumpy import ProcessState
from aiida import orm
from aiida.common import LinkType
from aiida.common import AttributeDict
from aiida.engine import ProcessHandlerReport
from aiida_pseudo.groups.family.pseudo import PseudoPotentialFamily
from aiida_siesta.calculations.siesta import SiestaCalculation
from aiida_siesta.workflows.base import SiestaBaseWorkChain
#from aiida_siesta.groups.pseudos import PsmlFamily


@pytest.fixture
def generate_workchain_base(generate_psml_data, fixture_code, fixture_localhost, generate_workchain, 
        generate_structure, generate_param, generate_basis, generate_kpoints_mesh,
        generate_calc_job_node, generate_parser, generate_psml_fam):
    """
    Generate an instance of a `SiestaBaseWorkChain`.
    The parameters:
    1) exit_code. This inputs triggers the generation of a SiestaCalculation through the 
       `generate_calc_job_node` fixture with a particular exit_code and it is attached to
       the current SiestaBaseWorkChain as children.
    2) remove_inp. An input to remove among the one standardly set. Special keyword accepted
       or the name of a defined port.
    3) add_pseudo_fam. Triggers the addition of a pseudo_family in inputs. The name of this
       pseudo family must be passed.
    Note that `remove_inp = "one_pseudo" and add_pseudo_fam != None` has a special meaning.
    """

    def _generate_workchain_base(exit_code=None, remove_inp=None, add_pseudo_fam=None):

        entry_point_wc = 'siesta.base'
        entry_point_code = 'siesta.siesta'

        psml = generate_psml_data('Si')

        inputs = {
            'code': fixture_code(entry_point_code),
            'structure': generate_structure(),
            'kpoints': generate_kpoints_mesh(2),
            'parameters': generate_param(),
            'basis': generate_basis(),
            'pseudos': {
                'Si': psml,
                'SiDiff': psml
            },
            'options': orm.Dict(dict={
               'resources': {'num_machines': 1  },
               'max_wallclock_seconds': 1800,
               'withmpi': False,
               })
        }

        if add_pseudo_fam is not None:
            generate_psml_fam(add_pseudo_fam,"Si")
            inputs['pseudo_family'] = orm.Str(add_pseudo_fam)

        if remove_inp is not None:
            if remove_inp == "max_wallclock_seconds":
                inputs["options"].delete_attribute("max_wallclock_seconds")
            elif remove_inp == "one_pseudo":
                # I override the pseudo fam with an empty one
                if add_pseudo_fam:
                    PseudoPotentialFamily.objects.get_or_create("pp")
                    inputs['pseudo_family'] = orm.Str("pp")
                    inputs.pop("pseudos")
                else:
                    inputs["pseudos"].pop('Si')
            else:
                inputs.pop(remove_inp)

        process = generate_workchain(entry_point_wc, inputs)

        if exit_code is not None:
            # Generate a SiestaCalculation node with exit code. The node comes
            # with`remote_folder` and retrieved as outputs (triggered by "default")
            inputs2 = AttributeDict({'structure': generate_structure()})
            attributes = AttributeDict({'input_filename':'aiida.fdf', 'output_filename':'aiida.out', 'prefix':'aiida'})
            node = generate_calc_job_node("siesta.siesta", fixture_localhost, "default", inputs2, attributes)
            #Set process state of the node
            node.set_process_state(ProcessState.FINISHED)
            node.set_exit_status(exit_code.status)

            process.ctx.iteration = 1
            process.ctx.children = [node]

        return process

    return _generate_workchain_base

def test_prepare_inputs(aiida_profile, generate_workchain_base):
    """
    Test `SiestaBaseWorkChain.prepare_inputs`. The logic inside the
    method is different whether there is a pseudo_family specified. 
    """
    process = generate_workchain_base()
    process.setup()
    process.prepare_inputs()

    assert isinstance(process.ctx.inputs, dict)

    process2 = generate_workchain_base(remove_inp="pseudos", add_pseudo_fam="tes")
    process2.setup()
    process2.prepare_inputs()

    assert isinstance(process2.ctx.inputs, dict)


def test_validators(aiida_profile, generate_workchain_base):
    """
    Test `SiestaBaseWorkChain` validators.
    """

    # Test the validator of the options input.
    with pytest.raises(ValueError):
        generate_workchain_base(remove_inp="max_wallclock_seconds")

    # Test the validator when pseudo is missing for one element.
    with pytest.raises(ValueError):
        generate_workchain_base(remove_inp="one_pseudo")

    # Test the validator that detects no ions, nor pseudos, nor pseudo_family is present.
    with pytest.raises(ValueError):
        generate_workchain_base(remove_inp="pseudos")

    # Test the validator when not all the required pseudos are in the family.
    with pytest.raises(ValueError):
        generate_workchain_base(remove_inp="one_pseudo", add_pseudo_fam="test1")

    # Test the validator when both pseudo_fam and pseudos are specified.
    with pytest.raises(ValueError):
        generate_workchain_base(add_pseudo_fam="test2")

    generate_workchain_base(remove_inp="pseudos", add_pseudo_fam="test3")

 
def test_handle_error_geom_not_conv(aiida_profile, generate_workchain_base):
    """
    Test `SiestaBaseWorkChain.handle_error_geom_not_conv`.
    """
    process = generate_workchain_base(exit_code=SiestaCalculation.exit_codes.GEOM_NOT_CONV)
    process.setup()
    process.prepare_inputs()

    #Add another fake output to the SiestaCalculation node
    calculation = process.ctx.children[-1]
    out_par = orm.Dict(dict={"variable_geometry":False})
    out_par.add_incoming(calculation, link_type=LinkType.CREATE, link_label='output_parameters')
    out_par.store()

    result = process.handle_error_geom_not_conv(calculation)
    assert isinstance(result, ProcessHandlerReport)
    assert result.do_break
    #assert result.exit_code == SiestaBaseWorkChain.exit_codes.GEOM_NOT_CONV

    #result = process.inspect_process()
    #assert result == PwBaseWorkChain.exit_codes.ERROR_UNRECOVERABLE_FAILURE

def test_handle_error_scf_not_conv(aiida_profile, generate_workchain_base):
    """
    Test `SiestaBaseWorkChain.handle_error_scf_not_conv`.
    """
    process = generate_workchain_base(exit_code=SiestaCalculation.exit_codes.SCF_NOT_CONV)
    process.setup()
    process.prepare_inputs()

    #Add another fake output to the SiestaCalculation node
    calculation = process.ctx.children[-1]
    out_par = orm.Dict(dict={"variable_geometry":False})
    out_par.add_incoming(calculation, link_type=LinkType.CREATE, link_label='output_parameters')
    out_par.store()

    result = process.handle_error_scf_not_conv(calculation)
    assert isinstance(result, ProcessHandlerReport)
    assert result.do_break
    #assert result.exit_code == SiestaBaseWorkChain.exit_codes.GEOM_NOT_CONV

    #result = process.inspect_process()
    #assert result == PwBaseWorkChain.exit_codes.ERROR_UNRECOVERABLE_FAILURE


def test_handle_error_basis_pol(aiida_profile, generate_workchain_base):
    """
    Test `SiestaBaseWorkChain.handle_error_basis_pol`.
    """
    process = generate_workchain_base(exit_code=SiestaCalculation.exit_codes.BASIS_POLARIZ)
    process.setup()
    process.prepare_inputs()

    result = process.handle_error_basis_pol(process.ctx.children[-1])
    assert isinstance(result, ProcessHandlerReport)
    assert result.do_break
    assert result.exit_code == SiestaBaseWorkChain.exit_codes.ERROR_BASIS_POL


def test_handle_error_bands(aiida_profile, generate_workchain_base):
    """
    Test `SiestaBaseWorkChain.handle_error_bands`.
    """
    process = generate_workchain_base(exit_code=SiestaCalculation.exit_codes.BANDS_PARSE_FAIL)
    process.setup()
    process.prepare_inputs()

    result = process.handle_error_bands(process.ctx.children[-1])
    assert isinstance(result, ProcessHandlerReport)
    assert result.do_break
    assert result.exit_code == SiestaBaseWorkChain.exit_codes.ERROR_BANDS_PARSING

    #result = process.inspect_process()
    #assert result == PwBaseWorkChain.exit_codes.ERROR_UNRECOVERABLE_FAILURE


def test_handle_error_split_norm(aiida_profile, generate_workchain_base):
    """
    Test `SiestaBaseWorkChain.handle_error_split_norm`.
    """
    process = generate_workchain_base(exit_code=SiestaCalculation.exit_codes.SPLIT_NORM)
    process.setup()
    process.prepare_inputs()

    #Add log info at the SiestaCalculation
    calculation = process.ctx.children[-1]
    calculation.logger.error("Error in split_norm option. Minimum value is 1")

    result = process.handle_error_split_norm(calculation)
    assert isinstance(result, ProcessHandlerReport)
    assert result.do_break

