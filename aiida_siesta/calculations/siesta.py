import os
from aiida import orm
from aiida.common import CalcInfo, CodeInfo
from aiida.common.constants import elements
from aiida.engine import CalcJob
from aiida.orm import Dict, StructureData, BandsData, ArrayData
from aiida_pseudo.data.pseudo.psf import PsfData
from aiida_pseudo.data.pseudo.psml import PsmlData
from aiida_siesta.utils.tkdict import FDFDict
from aiida_siesta.data.psf import PsfData as DeprecatedPsfData
from aiida_siesta.data.psml import PsmlData as DeprecatedPsmlData
from aiida_siesta.data.ion import IonData

# See the LICENSE.txt and AUTHORS.txt files.

###################################################################################
## Since aiida 1.0 There is now a clear distinction between Nodes and Processes. ##
## A calculation is now a process and it is treated as a Process class similar   ##
## to the WorkChains. Use of class variables & the input spec is necessary.      ##
###################################################################################


def internal_structure(structure, basis_dict=None):
    """
    Add the floating sites to the structure if necessary.
    Params:
    * structure. StructureData passed in input.
    * basis_dict. Python dictionary with the basis info passed in input (no Dict!!)
    Return three possible scenarios:
    1) a structure with added floating sites if they are specified in the basis dict
    2) a clone of the original structure if no floating sites are specified in the basis dict
    3) None if a floating site with the same name of a site in the original struture is present
    """

    tweaked = structure.clone()
    tweaked._internal_kind_tags = {}  #Nedded for a bug? Investigate!

    if basis_dict is not None:
        floating = basis_dict.get('floating_sites', None)
        if floating is not None:
            original_kind_names = [kind.name for kind in structure.kinds]
            for item in floating:
                if item["name"] in original_kind_names:
                    return None
                tweaked.append_atom(position=item["position"], symbols=item["symbols"], name=item["name"])

    return tweaked


def validate_pseudos(value, _):
    """
    Only used to throw deprecation warnings. Can be deleted in v2.0.0
    """
    if value:
        for key, val in value.items():
            if isinstance(val, (DeprecatedPsfData, DeprecatedPsmlData)):
                import warnings
                from aiida_siesta.utils.warn import AiidaSiestaDeprecationWarning
                message = (
                    f'You are using as pseudos for {key} a `PsfData/PsmlData` class from the aiida_siesta package. ' +
                    'These classes has been deprecated and will be removed in `v2.0.0`. ' +
                    'Use the same classes imported from `aiida_pseudo.data.pseudo`.'
                )
                warnings.warn(message, AiidaSiestaDeprecationWarning)

        return None


def validate_basis(value, _):
    """
    Validate basis input port. Only validates that `floating_sites`, if present,
    has the correct format.
    """
    # Before plumpy 0.17.0, the port was checked even if not required and the value
    # set to empty tuple if not passed. This is the reason of the first "if" statement.
    if value:
        if 'floating_sites' in value.get_dict():
            message = "wrong specification of floating_sites, "
            if not isinstance(value.get_dict()['floating_sites'], list):
                return message + "it must be a list of dictionaries."
            for item in value.get_dict()['floating_sites']:
                if not isinstance(item, dict):
                    return message + "it must be a list of dictionaries."
                if not all(x in item.keys() for x in ['name', 'symbols', 'position']):
                    return message + "'name', 'symbols' and 'position' must be specified."


def validate_structure(value, _):
    """
    Validate structure input port. It takes care to check that no alchemical atoms
    are passed, since they are not supported.
    """
    # Even though structure is mandatory here, other workchain might change this requirement
    # (see iterator) and therefore the "if" is still needed.
    if value:
        for kind in value.kinds:
            if len(kind.symbols) > 1:
                return "alchemical atoms not supported; structure must have one single symbol per kind."


def validate_parameters(value, _):
    """
    Validate parameters input port. Looks for blocked keywords (defined as attribute of SiestaCalculation)
    and that pao infos are not here (they belong to the basis Dict).
    """
    if value:
        input_params = FDFDict(value.get_dict())
        for key in input_params:
            if "pao" in key:
                return "you can't have PAO options in the parameters input port, they belong to the basis input port."
            if key in SiestaCalculation._aiida_blocked_keywords:
                message = (
                    f"you can't specify explicitly the '{input_params.get_last_untranslated_key(key)}' flag " +
                    "in the input parameters."
                )
                return message


def validate_kpoints(value, _):
    """
    Validate kpoints input port. Checks the mesh is set.
    """
    if value:
        mesh = value.get_attribute("mesh", None)
        if mesh is None:
            return "kpoints sampling for scf must be given in mesh form, use `set_kpoints_mesh`."


def validate_bandskpoints(value, _):
    """
    Validate bandskpoints input port. Checks the kpoints list is set.
    """
    if value:
        try:
            value.get_kpoints()
        except AttributeError:
            return "bandskpoints requires a list of kpoints, use `set_kpoints`."


def bandskpoints_warnings(value):
    """
    Called in validate_inputs. Only issue warnings.
    """
    import warnings

    if "bandskpoints" in value:
        bandskpoints = value["bandskpoints"]
        input_params = FDFDict(value["parameters"].get_dict())
        # We send a warning if user set a cell in `bandskpoints` and this cell is not the input cell.
        # This cell is anyway ignored since the inputs or output structure are used for the kpoints path.
        kpcell = bandskpoints.get_attribute("cell", None)
        if kpcell:
            if kpcell != value["structure"].cell:
                warnings.warn('The cell set in `bandskpoints` is ignored! Overridden by output or input structure.')
        #second we rise a warning about consequences when the cell is relaxed
        var_cell_keys = [FDFDict.translate_key("md-variable-cell"), FDFDict.translate_key("md-constant-volume")]
        var_cell_keys.append(FDFDict.translate_key("md-relax-cell-only"))
        for key in input_params:
            if key in var_cell_keys:
                logline = (
                    "Requested calculation of bands after a relaxation with variable cell! " +
                    "Are you sure you are happy about the selected kpoints for bands? Cell symmetry might change! " +
                    "It is suggested to use the `BandGapWorkChain`."
                )
                if isinstance(input_params[key], str):
                    if FDFDict.translate_key(input_params[key]) in ["t", "true", "yes", ".true."]:
                        warnings.warn(logline)
                        break
                else:
                    if input_params[key] is True:
                        warnings.warn(logline)
                        break


def validate_inputs(value, _):
    """
    Validate the entire input namespace. It takes care to ckeck the consistency
    and compatibility of the inputed basis, pseudos, and ions.
    Also calls the `bandskpoints_warnings` that issues warning about bandskpoints selection.
    """
    import warnings

    bandskpoints_warnings(value)

    if 'ions' in value:
        quantity = 'ions'
        if 'pseudos' in value:
            warnings.warn("At least one ion file in input, all the pseudos will be ignored")
    else:
        if 'pseudos' not in value:
            return "No pseudopotentials nor ions specified in input"
        quantity = 'pseudos'

    if 'basis' in value:
        structure = internal_structure(value["structure"], value["basis"].get_dict())
        if structure is None:
            return "Not possibe to specify `floating_sites` (ghosts) with the same name of a structure kind."
    else:
        structure = value["structure"]

    #Check each kind in the structure (including freshly added ghosts) have a corresponding pseudo or ion
    kinds = [kind.name for kind in structure.kinds]
    if set(kinds) != set(value[quantity].keys()):
        ps_io = ', '.join(list(value[quantity].keys()))
        kin = ', '.join(list(kinds))
        string_out = (
            'mismatch between defined pseudos/ions and the list of kinds of the structure\n' +
            f' pseudos/ions: {ps_io} \n kinds(including ghosts): {kin}'
        )
        return string_out


class SiestaCalculation(CalcJob):
    """
    Siesta calculator class for AiiDA.
    """

    # Class attributes: filepaths of certain outputs
    _JSON_FILE = 'time.json'
    _MESSAGES_FILE = 'MESSAGES'
    _BASIS_ENTHALPY_FILE = 'BASIS_ENTHALPY'

    # Class attributes: default of the input.spec...just default, but user could change the name
    _DEFAULT_PREFIX = 'aiida'
    _DEFAULT_INPUT_FILE = 'aiida.fdf'
    _DEFAULT_OUTPUT_FILE = 'aiida.out'

    # Class attribute: elements to copy from the parent in restarts (fow now, just the density matrix file)
    _restart_copy_from = os.path.join('./', '*.DM')

    # Class attribute: in restarts, it will copy the previous elements in the following folder
    _restart_copy_to = './'

    # Class attribute: blocked keywords
    _readable_blocked = [
        'system-name',
        'system-label',
        'number-of-species',
        'number-of-atoms',
        'lattice-constant',
        'atomic-coordinates-format',
        'use-tree-timer',
        'xml-write',
        'dm-use-save-dm',
        'geometry-must-converge',
        'user-basis',
        'lua-script',
        'max-walltime',
    ]
    _aiida_blocked_keywords = [FDFDict.translate_key(key) for key in _readable_blocked]

    @classmethod
    def define(cls, spec):
        super().define(spec)

        # Input nodes
        spec.input('code', valid_type=orm.Code, help='Input code')
        spec.input('structure', valid_type=orm.StructureData, help='Input structure', validator=validate_structure)
        spec.input(
            'kpoints', valid_type=orm.KpointsData, help='Input kpoints', required=False, validator=validate_kpoints
        )
        spec.input(
            'bandskpoints',
            valid_type=orm.KpointsData,
            help='Input kpoints for bands',
            required=False,
            validator=validate_bandskpoints
        )
        spec.input('basis', valid_type=orm.Dict, help='Input basis', required=False, validator=validate_basis)
        spec.input('settings', valid_type=orm.Dict, help='Input settings', required=False)
        spec.input('parameters', valid_type=orm.Dict, help='Input parameters', validator=validate_parameters)
        spec.input('parent_calc_folder', valid_type=orm.RemoteData, required=False, help='Parent folder')
        spec.input_namespace(
            'pseudos',
            valid_type=(PsfData, PsmlData, DeprecatedPsfData, DeprecatedPsmlData),
            help='Input pseudo potentials',
            dynamic=True,
            required=False,
            validator=validate_pseudos
        )
        spec.input_namespace('ions', valid_type=IonData, help='Input ion file', dynamic=True, required=False)

        # Input namespace for Lua-related material.
        # Parameters are in a separate dictionary to enable a reduced set of 'universal' scripts for particular uses.
        # Input files (e.g., image files for NEB) should be packaged in a FolderData object.
        # Files to be retrieved should be specified in a list o# path specifications.
        spec.input_namespace('lua', help='Script and files for the Lua engine')
        spec.input('lua.script', valid_type=orm.SinglefileData, required=False)
        spec.input('lua.parameters', valid_type=orm.Dict, required=False)
        spec.input('lua.input_files', valid_type=orm.FolderData, required=False)
        spec.input('lua.retrieve_list', valid_type=orm.List, required=False)

        # Metadada.options host the inputs that are not stored as a separate node, but attached to `CalcJobNode`
        # as attributes. They are optional, since a default is specified, but they might be changed by the user.
        # The first one is siesta specific. The others are defined in the CalcJob, here we change the default.
        spec.input('metadata.options.prefix', valid_type=str, default=cls._DEFAULT_PREFIX)
        spec.inputs['metadata']['options']['input_filename'].default = cls._DEFAULT_INPUT_FILE
        spec.inputs['metadata']['options']['output_filename'].default = cls._DEFAULT_OUTPUT_FILE
        spec.inputs['metadata']['options']['parser_name'].default = 'siesta.parser'

        # Global validator for the inputs
        spec.inputs.validator = validate_inputs

        # Output nodes
        spec.output('output_parameters', valid_type=Dict, required=True, help='The calculation results')
        spec.output('output_structure', valid_type=StructureData, required=False, help='Optional relaxed structure')
        spec.output('bands', valid_type=BandsData, required=False, help='Optional band structure')
        spec.output('forces_and_stress', valid_type=ArrayData, required=False, help='Optional forces and stress')
        spec.output_namespace('ion_files', valid_type=IonData, dynamic=True, required=False)

        # Option that allows access through node.res should be existing output node and a Dict
        spec.default_output_node = 'output_parameters'

        # Exit codes for specific errors. Useful for error handeling in workchains
        spec.exit_code(453, 'BANDS_PARSE_FAIL', message='Failure while parsing the bands file')
        spec.exit_code(452, 'BANDS_FILE_NOT_PRODUCED', message='Bands analysis was requested, but file is not present')
        spec.exit_code(450, 'SCF_NOT_CONV', message='Calculation did not reach scf convergence!')
        spec.exit_code(451, 'GEOM_NOT_CONV', message='Calculation did not reach geometry convergence!')
        spec.exit_code(350, 'UNEXPECTED_TERMINATION', message='Statement "Job completed" not detected, unknown error')
        spec.exit_code(449, 'SPLIT_NORM', message='Split_norm parameter too small')
        spec.exit_code(448, 'BASIS_POLARIZ', message='Problems in the polarization of a basis element')

    def initialize(self):
        """
        Some initialization (called at the beginning of `prepare_for_submission`:
        1) Create an internal structure where possible `floating_sites` are added.
        2) Create a list containing floating_species_names.
        3) Remove the `floating_sites` to the basis dictionary.
        4) Checks whether info on basis and pseudos are passed directly as ion files,
           in that case, cancel any info passed in the basis input.
        """
        value = self.inputs

        structure = internal_structure(value["structure"])
        floating_species_names = []

        basis_dict = None
        if 'basis' in value:
            basis_dict = value["basis"].get_dict()
            floating = basis_dict.pop('floating_sites', None)
            if floating is not None:
                for item in floating:
                    structure.append_atom(position=item["position"], symbols=item["symbols"], name=item["name"])
                    floating_species_names.append(item["name"])

        if 'ions' in value:
            basis_dict = None
            ion_or_pseudo = 'ions'
        else:
            ion_or_pseudo = 'pseudos'

        return structure, basis_dict, floating_species_names, ion_or_pseudo

    def prepare_for_submission(self, folder):  # noqa: MC0001  - is mccabe too complex funct -
        """
        Create the input files from the input nodes passed to this instance of the `CalcJob`.
        :param folder: an `aiida.common.folders.Folder` to temporarily write files on disk
        :return: `aiida.common.datastructures.CalcInfo` instance
        """

        # ============================ Initializations =============================
        # All input ports are validated, here asses their presence in case optional.

        code = self.inputs.code

        # self.initialize preprocess structure and basis. Decides whether use ions or pseudos
        structure, basis_dict, floating_species_names, ion_or_pseudo_str = self.initialize()

        ion_or_pseudo = self.inputs[ion_or_pseudo_str]

        parameters = self.inputs.parameters

        if 'kpoints' in self.inputs:
            kpoints = self.inputs.kpoints
        else:
            kpoints = None

        # As internal convention, the keys of the settings dict are uppercase
        if 'settings' in self.inputs:
            settings = self.inputs.settings.get_dict()
            settings_dict = {str(k).upper(): v for (k, v) in settings.items()}
        else:
            settings_dict = {}

        if 'bandskpoints' in self.inputs:
            bandskpoints = self.inputs.bandskpoints
        else:
            bandskpoints = None

        if 'parent_calc_folder' in self.inputs:
            parent_calc_folder = self.inputs.parent_calc_folder
        else:
            parent_calc_folder = None

        lua_inputs = self.inputs.lua

        if 'script' in lua_inputs:
            lua_script = lua_inputs.script
        else:
            lua_script = None

        if 'parameters' in lua_inputs:
            lua_parameters = lua_inputs.parameters
        else:
            lua_parameters = None

        if 'input_files' in lua_inputs:
            lua_input_files = lua_inputs.input_files
        else:
            lua_input_files = None

        if 'retrieve_list' in lua_inputs:
            lua_retrieve_list = lua_inputs.retrieve_list
        else:
            lua_retrieve_list = None

        # List of files to copy in the folder where the calculation runs, e.g. pseudo files
        local_copy_list = []

        # List of files for restart
        remote_copy_list = []

        # ================ Preprocess of input parameters =================

        input_params = FDFDict(parameters.get_dict())
        input_params.update({'system-name': self.inputs.metadata.options.prefix})
        input_params.update({'system-label': self.inputs.metadata.options.prefix})
        input_params.update({'use-tree-timer': 'T'})
        input_params.update({'xml-write': 'T'})
        input_params.update({'number-of-species': len(structure.kinds)})
        input_params.update({'number-of-atoms': len(structure.sites)})
        input_params.update({'geometry-must-converge': 'T'})
        input_params.update({'lattice-constant': '1.0 Ang'})
        input_params.update({'atomic-coordinates-format': 'Ang'})
        if lua_script is not None:
            input_params.update({'md-type-of-run': 'Lua'})
            input_params.update({'lua-script': lua_script.filename})
            local_copy_list.append((lua_script.uuid, lua_script.filename, lua_script.filename))
        if lua_input_files is not None:
            # Copy the whole contents of the FolderData object
            for file in lua_input_files.list_object_names():
                local_copy_list.append((lua_input_files.uuid, file, file))
        if ion_or_pseudo_str == "ions":
            input_params.update({'user-basis': 'T'})
        # NOTES:
        # 1) The lattice-constant parameter must be 1.0 Ang to impose the units and consider
        #   that the dimenstions of the lattice vectors are already correct with no need of alat.
        #   This breaks the band-k-points "pi/a" option. The use of this option is banned.
        # 2) The implicit coordinate convention of the StructureData class corresponds to the "Ang"
        #   convention in Siesta. That is why "atomic-coordinates-format" is blocked and reset.
        # 3) The Siesta code doesn't raise any warining if the geometry is not converged, unless
        #   the keyword geometry-must-converge is set. That's why it is always added.

        # ============================ Preparation of input data =================================

        # -------------------------------- CELL_PARAMETERS ---------------------------------------
        cell_parameters_card = "%block lattice-vectors\n"
        for vector in structure.cell:
            cell_parameters_card += ("{0:18.10f} {1:18.10f} {2:18.10f}" "\n".format(*vector))
        cell_parameters_card += "%endblock lattice-vectors\n"

        # ----------------------------ATOMIC_SPECIES & PSEUDOS/IONS-------------------------------
        atomic_species_card_list = []
        # Dictionary to get the atomic number of a given element
        datmn = {v['symbol']: k for k, v in elements.items()}
        spind = {}
        spcount = 0
        for kind in structure.kinds:
            spcount += 1  # species count
            spind[kind.name] = spcount
            atomic_number = datmn[kind.symbol]
            # Siesta expects negative atomic numbers for floating species
            if kind.name in floating_species_names:
                atomic_number = -atomic_number
            #Create the core of the chemicalspecieslabel block
            atomic_species_card_list.append(
                "{0:5} {1:5} {2:5}\n".format(spind[kind.name], atomic_number, kind.name.rjust(6))
            )
            psp_or_ion = ion_or_pseudo[kind.name]
            # Add pseudo (ion) file to the list of files to copy (create), with the appropiate name.
            # In the case of sub-species (different kind.name but same kind.symbol, e.g., 'C_surf',
            # sharing the same pseudo with 'C'), we copy the file ('C.psf') twice, once as 'C.psf',
            # and once as 'C_surf.psf'. This is required by Siesta.
            # It is passed as list of tuples with format ('node_uuid', 'filename', 'relativedestpath').
            # Since no subfolder is present in Siesta for pseudos, filename == relativedestpath.
            if isinstance(psp_or_ion, IonData):
                file_name = kind.name + ".ion"
                with folder.open(file_name, 'w', encoding='utf8') as handle:
                    handle.write(psp_or_ion.get_content_ascii_format())
            if isinstance(psp_or_ion, (PsfData, DeprecatedPsfData)):
                local_copy_list.append((psp_or_ion.uuid, psp_or_ion.filename, kind.name + ".psf"))
            if isinstance(psp_or_ion, (PsmlData, DeprecatedPsmlData)):
                local_copy_list.append((psp_or_ion.uuid, psp_or_ion.filename, kind.name + ".psml"))
        atomic_species_card_list = (["%block chemicalspecieslabel\n"] + list(atomic_species_card_list))
        atomic_species_card = "".join(atomic_species_card_list)
        atomic_species_card += "%endblock chemicalspecieslabel\n"
        # Free memory
        del atomic_species_card_list

        # -------------------------------------- ATOMIC_POSITIONS -----------------------------------
        atomic_positions_card_list = ["%block atomiccoordinatesandatomicspecies\n"]
        countatm = 0
        for site in structure.sites:
            countatm += 1
            atomic_positions_card_list.append(
                "{0:18.10f} {1:18.10f} {2:18.10f} {3:4} {4:6} {5:6}\n".format(
                    site.position[0], site.position[1], site.position[2], spind[site.kind_name],
                    site.kind_name.rjust(6), countatm
                )
            )
        atomic_positions_card = "".join(atomic_positions_card_list)
        del atomic_positions_card_list  # Free memory
        atomic_positions_card += "%endblock atomiccoordinatesandatomicspecies\n"

        # --------------------------------------- K-POINTS ----------------------------------------
        # It is optional, if not specified, gamma point only is performed (default of siesta)
        if kpoints is not None:
            mesh, offset = kpoints.get_kpoints_mesh()
            kpoints_card_list = ["%block kgrid_monkhorst_pack\n"]
            kpoints_card_list.append("{0:6} {1:6} {2:6} {3:18.10f}\n".format(mesh[0], 0, 0, offset[0]))
            kpoints_card_list.append("{0:6} {1:6} {2:6} {3:18.10f}\n".format(0, mesh[1], 0, offset[1]))
            kpoints_card_list.append("{0:6} {1:6} {2:6} {3:18.10f}\n".format(0, 0, mesh[2], offset[2]))
            kpoints_card = "".join(kpoints_card_list)
            kpoints_card += "%endblock kgrid_monkhorst_pack\n"
            del kpoints_card_list

        # ------------------------------------ K-POINTS-FOR-BANDS ----------------------------------
        # Two possibility are supported in Siesta: BandLines ad BandPoints.
        # User can't choose directly one of the two options, BandsLine is set automatically
        # if bandskpoints has labels, BandsPoints if bandskpoints has no labels.
        # BandLinesScale=pi/a not supported because a=1 always. BandLinesScale ReciprocalLatticeVectors
        # always set.
        if bandskpoints is not None:
            #the band line scale
            bandskpoints_card_list = ["BandLinesScale ReciprocalLatticeVectors\n"]
            #set the BandPoints
            if bandskpoints.labels is None:
                bandskpoints_card_list.append("%block BandPoints\n")
                for kpo in bandskpoints.get_kpoints():
                    bandskpoints_card_list.append("{0:8.3f} {1:8.3f} {2:8.3f} \n".format(kpo[0], kpo[1], kpo[2]))
                fbkpoints_card = "".join(bandskpoints_card_list)
                fbkpoints_card += "%endblock BandPoints\n"
            #set the BandLines
            else:
                bandskpoints_card_list.append("%block BandLines\n")
                savindx = []
                listforbands = bandskpoints.get_kpoints()
                for indx, label in bandskpoints.labels:
                    savindx.append(indx)
                rawindex = 0
                for indx, label in bandskpoints.labels:
                    rawindex = rawindex + 1
                    x, y, z = listforbands[indx]
                    if rawindex == 1:
                        bandskpoints_card_list.append(
                            "{0:3} {1:8.3f} {2:8.3f} {3:8.3f} {4:1} \n".format(1, x, y, z, label)
                        )
                    else:
                        bandskpoints_card_list.append(
                            "{0:3} {1:8.3f} {2:8.3f} {3:8.3f} {4:1} \n".format(
                                indx - savindx[rawindex - 2], x, y, z, label
                            )
                        )
                fbkpoints_card = "".join(bandskpoints_card_list)
                fbkpoints_card += "%endblock BandLines\n"
            del bandskpoints_card_list

        # ================================= Operations for restart =================================
        # The presence of a 'parent_calc_folder' input node signals that we want to
        # get something from there, as indicated in the self._restart_copy_from attribute.
        # In Siesta's case, for now, just the density-matrix file is copied
        # to the current calculation's working folder.
        # ISSUE: Is this mechanism flexible enough? An alternative would be to
        # pass the information about which file(s) to copy in the metadata.options dictionary
        if parent_calc_folder is not None:
            remote_copy_list.append((
                parent_calc_folder.computer.uuid,
                os.path.join(parent_calc_folder.get_remote_path(), self._restart_copy_from), self._restart_copy_to
            ))
            input_params.update({'dm-use-save-dm': "T"})

        # ===================================== FDF file creation ====================================

        # To have easy access to inputs metadata options
        metadataoption = self.inputs.metadata.options

        # input_filename = self.inputs.metadata.options.input_filename
        input_filename = folder.get_abs_path(metadataoption.input_filename)

        # Print to file
        with open(input_filename, 'w') as infile:
            # Parameters
            for k, v in sorted(input_params.get_filtered_items()):
                infile.write("%s %s\n" % (k, v))
            # Basis set info is processed just like the general parameters section.
            if basis_dict:  #It migh also be empty dict. In such case we do not write.
                infile.write("#\n# -- Basis Set Info follows\n#\n")
                for k, v in basis_dict.items():
                    infile.write("%s %s\n" % (k, v))
            # Write previously generated cards now
            infile.write("#\n# -- Structural Info follows\n#\n")
            infile.write(atomic_species_card)
            infile.write(cell_parameters_card)
            infile.write(atomic_positions_card)
            if kpoints is not None:
                infile.write("#\n# -- K-points Info follows\n#\n")
                infile.write(kpoints_card)
            if bandskpoints is not None:
                infile.write("#\n# -- Bandlines/Bandpoints Info follows\n#\n")
                infile.write(fbkpoints_card)
            # Write max wall-clock time
            # This should prevent SiestaCalculation from being terminated by scheduler, however the
            # strategy is not 100% effective since SIESTA checks the simulation time versus max-walltime
            # only at the end of each SCF and geometry step. The scheduler might kill the process in between.
            infile.write("#\n# -- Max wall-clock time block\n#\n")
            infile.write(f"maxwalltime {metadataoption.max_wallclock_seconds}\n")

        # ================================== Lua parameters file ===================================

        if lua_parameters is not None:
            lua_config_filename = folder.get_abs_path("config.lua")
            # Generate a 'config.lua' file with Lua syntax
            with open(lua_config_filename, 'w') as f_lua:
                f_lua.write("--- Lua script parameters \n")
                for k, v in lua_parameters.get_dict().items():
                    if isinstance(v, str):
                        f_lua.write('%s = "%s"\n' % (k, v))
                    else:
                        f_lua.write("%s = %s\n" % (k, v))

        # ============================= Code and Calc info =========================================
        # Code information object and Calc information object are now
        # only used to set up the CMDLINE (the bash line that launches siesta)
        # and to set up the list of files to retrieve.

        cmdline_params = settings_dict.pop('CMDLINE', [])

        codeinfo = CodeInfo()
        codeinfo.cmdline_params = list(cmdline_params)
        codeinfo.stdin_name = metadataoption.input_filename
        codeinfo.stdout_name = metadataoption.output_filename
        codeinfo.code_uuid = code.uuid

        calcinfo = CalcInfo()
        calcinfo.uuid = str(self.uuid)
        calcinfo.local_copy_list = local_copy_list
        calcinfo.remote_copy_list = remote_copy_list
        calcinfo.codes_info = [codeinfo]
        # Retrieve by default: the output file, the xml file, the messages file, and the json timing file.
        # If bandskpoints, also the bands file is added to the retrieve list.
        calcinfo.retrieve_list = []
        xml_file = str(metadataoption.prefix) + ".xml"
        bands_file = str(metadataoption.prefix) + ".bands"
        calcinfo.retrieve_list.append(metadataoption.output_filename)
        calcinfo.retrieve_list.append(xml_file)
        calcinfo.retrieve_list.append(self._JSON_FILE)
        calcinfo.retrieve_list.append(self._MESSAGES_FILE)
        calcinfo.retrieve_list.append(self._BASIS_ENTHALPY_FILE)
        calcinfo.retrieve_list.append("*.ion.xml")

        if bandskpoints is not None:
            calcinfo.retrieve_list.append(bands_file)

        if lua_retrieve_list is not None:
            calcinfo.retrieve_list += lua_retrieve_list.get_list()

        # If we ever want to avoid having the config.lua file in the repository,
        # since the information is already in the lua_parameters dictionary:
        # if lua_parameters is not None:
        #    calcinfo.provenance_exclude_list = ['config.lua']

        # Any other files specified in the settings dictionary
        settings_retrieve_list = settings_dict.pop('ADDITIONAL_RETRIEVE_LIST', [])
        calcinfo.retrieve_list += settings_retrieve_list

        return calcinfo

    @classmethod
    def inputs_generator(cls):  # pylint: disable=no-self-argument,no-self-use
        from aiida_siesta.utils.protocols_system.input_generators import SiestaCalculationInputGenerator
        return SiestaCalculationInputGenerator(cls)
