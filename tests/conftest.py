from __future__ import absolute_import


# -*- coding: utf-8 -*-
# pylint: disable=redefined-outer-name
"""Initialise a text database and profile for pytest."""
"""Courtesy of Sebastian Huber, aiida-quantumespresso"""
import io
import os
import collections
import pytest
import six

pytest_plugins = ['aiida.manage.tests.pytest_fixtures']  # pylint: disable=invalid-name
#Here there is aiida_profile, aiida_localhost 
#Strange way to call it, it is the way of pytest https://docs.pytest.org/en/latest/plugins.html

@pytest.fixture(scope='function')
def fixture_sandbox():
    """Return a `SandboxFolder`."""
    from aiida.common.folders import SandboxFolder
    with SandboxFolder() as folder:
        yield folder


@pytest.fixture
def fixture_localhost(aiida_localhost):
    """Return a localhost `Computer`."""
    localhost = aiida_localhost
    localhost.set_default_mpiprocs_per_machine(1)
    return localhost


@pytest.fixture
def fixture_code(fixture_localhost):
    """Return a `Code` instance configured to run calculations of given entry point on localhost `Computer`."""

    def _fixture_code(entry_point_name):
        from aiida.orm import Code
        return Code(input_plugin_name=entry_point_name, remote_computer_exec=[fixture_localhost, '/bin/true'])

    return _fixture_code


@pytest.fixture
def generate_calc_job():
    """Fixture to construct a new `CalcJob` instance and call `prepare_for_submission` for testing `CalcJob` classes.
    The fixture will return the `CalcInfo` returned by `prepare_for_submission` and the temporary folder that was passed
    to it, into which the raw input files will have been written.
    """

    def _generate_calc_job(folder, entry_point_name, inputs=None):
        """Fixture to generate a mock `CalcInfo` for testing calculation jobs."""
        from aiida.engine.utils import instantiate_process
        from aiida.manage.manager import get_manager
        from aiida.plugins import CalculationFactory

        manager = get_manager()
        runner = manager.get_runner()

        process_class = CalculationFactory(entry_point_name)
        process = instantiate_process(runner, process_class, **inputs)

        calc_info = process.prepare_for_submission(folder)

        return calc_info

    return _generate_calc_job


@pytest.fixture
def generate_calc_job_node():
    """Fixture to generate a mock `CalcJobNode` for testing parsers."""

    def flatten_inputs(inputs, prefix=''):
        """Flatten inputs recursively like :meth:`aiida.engine.processes.process::Process._flatten_inputs`."""
        flat_inputs = []
        for key, value in six.iteritems(inputs):
            if isinstance(value, collections.abc.Mapping):
                flat_inputs.extend(flatten_inputs(value, prefix=prefix + key + '__'))
            else:
                flat_inputs.append((prefix + key, value))
        return flat_inputs

    def _generate_calc_job_node(entry_point_name, computer, test_name=None, inputs=None, attributes=None):
        """Fixture to generate a mock `CalcJobNode` for testing parsers.
        :param entry_point_name: entry point name of the calculation class
        :param computer: a `Computer` instance
        :param test_name: relative path of directory with test output files in the `fixtures/{entry_point_name}` folder.
        :param inputs: any optional nodes to add as input links to the corrent CalcJobNode
        :param attributes: any optional attributes to set on the node
        :return: `CalcJobNode` instance with an attached `FolderData` as the `retrieved` node
        """
        from aiida import orm
        from aiida.common import LinkType
        from aiida.plugins.entry_point import format_entry_point_string

        entry_point = format_entry_point_string('aiida.calculations', entry_point_name)

        node = orm.CalcJobNode(computer=computer, process_type=entry_point)
        #This should be defined through input line
        #node.set_attribute('input_filename', 'aiida.fdf')
        #node.set_attribute('output_filename', 'aiida.out')
        #node.set_attribute('prefix', 'aiida')
        node.set_option('resources', {'num_machines': 1, 'num_mpiprocs_per_machine': 1})
        node.set_option('max_wallclock_seconds', 1800)

        if attributes:
            node.set_attribute_many(attributes)
        
        #What inputs do we need? I don't think it checks the mandatory inputs,
        #for instance the pseudo is not defined in quantum espresso.
        #Probably only the ones that trigger a particular parsing? Or not even.
        if inputs:
            for link_label, input_node in flatten_inputs(inputs):
                input_node.store()
                node.add_incoming(input_node, link_type=LinkType.INPUT_CALC, link_label=link_label)

        node.store()

        if test_name is not None:
            basepath = os.path.dirname(os.path.abspath(__file__))
            filepath = os.path.join(
                basepath, 'parsers', 'fixtures', entry_point_name[len('siesta.'):], test_name
            )

            retrieved = orm.FolderData()
            retrieved.put_object_from_tree(filepath)
            retrieved.add_incoming(node, link_type=LinkType.CREATE, link_label='retrieved')
            retrieved.store()

            remote_folder = orm.RemoteData(computer=computer, remote_path='/tmp')
            remote_folder.add_incoming(node, link_type=LinkType.CREATE, link_label='remote_folder')
            remote_folder.store()

        return node

    return _generate_calc_job_node


@pytest.fixture(scope='session')
def generate_psf_data():
    """Return a `PsfData` instance for the given element a file for which should exist in `tests/pseudos`."""

    def _generate_psf_data(element):
        """Return `PsfData` node."""
        #from aiida_siesta.data.psf import PsfData
        from aiida_pseudo.data.pseudo.psf import PsfData 

        filename = os.path.join('tests', 'fixtures',  'pseudos', '{}.psf'.format(element))
        filepath = os.path.abspath(filename)

        with io.open(filepath, 'rb') as handle:
            #psf = PsfData(file=handle.name)
            psf = PsfData(handle)

        return psf

    return _generate_psf_data


@pytest.fixture(scope='session')
def generate_psml_data():
    """Return a `PsmlData` instance for the given element a file for which should exist in `tests/pseudos`."""

    def _generate_psml_data(element):
        """Return `PsmlData` node."""
        from aiida_pseudo.data.pseudo.psml import PsmlData

        filename = os.path.join('tests', 'fixtures', 'pseudos', '{}.psml'.format(element))
        filepath = os.path.abspath(filename)

        with io.open(filepath, 'rb') as handle:
            psml = PsmlData(handle)

        return psml

    return _generate_psml_data


@pytest.fixture(scope='session')
def generate_ion_data():
    """Return a `PsmlData` instance for the given element a file for which should exist in `tests/ions`."""

    def _generate_ion_data(element):
        """Return `IonData` node."""
        from aiida_siesta.data.ion import IonData

        filename = os.path.join('tests', 'fixtures', 'ions', '{}.ion.xml'.format(element))
        filepath = os.path.abspath(filename)

        with io.open(filepath, 'r') as handle:
            ion = IonData(file=handle.name)

        return ion

    return _generate_ion_data


@pytest.fixture(scope='session')
def generate_lua_file():
    """Return a `SingleData` instance containing the lua file `lua_scripts/relax_geometry_lbfgs.lua`."""

    def _generate_lua_file():
        """Return `SingleData` node."""
        from aiida.orm import SinglefileData

        filename = os.path.join('tests', 'fixtures', 'lua_scripts', 'relax_geometry_lbfgs.lua')
        filepath = os.path.abspath(filename)

        lua_file = SinglefileData(filepath)

        return lua_file

    return _generate_lua_file


@pytest.fixture(scope='session')
def generate_lua_folder():
    """Return a `FolderData` instance containing extra lua files `lua_scripts/neb-data`."""

    def _generate_lua_folder():
        """Return `FolderData` node."""
        from aiida.orm import FolderData

        foldername = os.path.join('tests', 'fixtures', 'lua_scripts', 'neb-data')
        folderpath = os.path.abspath(foldername)

        lua_folder = FolderData(tree=folderpath)

        return lua_folder

    return _generate_lua_folder


@pytest.fixture(scope='session')
def generate_psml_fam(generate_psml_data):
    """Return a `PsmlData` instance for the given element a file for which should exist in `tests/pseudos`."""

    def _generate_psml_fam(fam_name, element):
        """Return `PsmlData` node."""
       
        from aiida_pseudo.groups.family.pseudo import PseudoPotentialFamily
        #from aiida_siesta.groups.pseudos import PsmlFamily

        group, created = PseudoPotentialFamily.objects.get_or_create(fam_name)
        psml = generate_psml_data(element)
        psml.store()
        group.add_nodes([psml])


    return _generate_psml_fam


@pytest.fixture
def generate_structure():
    """Return a `StructureData` representing bulk silicon."""

    def _generate_structure(scale=None):
        """Return a `StructureData` representing bulk silicon."""
        from aiida.orm import StructureData

        param = 5.43
        cell = [[param / 2., param / 2., 0], [param / 2., 0, param / 2.], [0, param / 2., param / 2.]]
        structure = StructureData(cell=cell)
        structure.append_atom(position=(0., 0., 0.), symbols='Si', name='Si')
        structure.append_atom(position=(param / 4., param / 4., param / 4.), symbols='Si', name='SiDiff')

        if scale:
            the_ase = structure.get_ase()
            new_ase = the_ase.copy()
            new_ase.set_cell(the_ase.get_cell() * float(scale), scale_atoms=True)
            new_structure = StructureData(ase=new_ase)
            structure = new_structure

        return structure

    return _generate_structure

@pytest.fixture
def generate_param():
    """Return a `Dict` with standard parameters."""

    def _generate_param():
        """Return a `Dict` with standard parameters."""
        from aiida.orm import Dict

        parameters = {
        'xc-functional': 'LDA',
        'xc-authors': 'CA',
        'max-scfiterations': 50,
        'dm-numberpulay': 4,
        'dm-mixingweight': 0.3,
        'dm-tolerance': 1.e-3,
        'Solution-method': 'diagon',
        'electronic-temperature': '25 meV',
        'md-typeofrun': 'cg',
        'md-numcgsteps': 3,
        'md-maxcgdispl': '0.1 Ang',
        'md-maxforcetol': '0.04 eV/Ang'}

        return Dict(dict=parameters)

    return _generate_param

@pytest.fixture
def generate_basis():
    """Return a `Dict` with basis."""

    def _generate_basis():
        """Return a `Dict` with basis."""
        from aiida.orm import Dict

        basis = {
        'pao-energy-shift': '300 meV',
        '%block pao-basis-sizes': """
        Si DZP
        SiDiff DZP
        %endblock pao-basis-sizes""",
        }

        return Dict(dict=basis)

    return _generate_basis


@pytest.fixture
def generate_kpoints_mesh():
    """Return a `KpointsData` node."""

    def _generate_kpoints_mesh(npoints):
        """Return a `KpointsData` with a mesh of npoints in each direction."""
        from aiida.orm import KpointsData

        kpoints = KpointsData()
        kpoints.set_kpoints_mesh([npoints] * 3)

        return kpoints

    return _generate_kpoints_mesh


@pytest.fixture(scope='session')
def generate_parser():
    """Fixture to load a parser class for testing parsers."""

    def _generate_parser(entry_point_name):
        """Fixture to load a parser class for testing parsers.
        :param entry_point_name: entry point name of the parser class
        :return: the `Parser` sub class
        """
        from aiida.plugins import ParserFactory
        return ParserFactory(entry_point_name)

    return _generate_parser


@pytest.fixture
def generate_remote_data():
    """Return a `RemoteData` node."""

    def _generate_remote_data(computer, remote_path, entry_point_name=None):
        """Generate a RemoteData node, loctated at remote_path"""
        from aiida.common.links import LinkType
        from aiida.orm import CalcJobNode, RemoteData
        from aiida.plugins.entry_point import format_entry_point_string

        entry_point = format_entry_point_string('aiida.calculations', entry_point_name)

        remote = RemoteData(remote_path=remote_path)
        remote.computer = computer

        if entry_point_name is not None:
            creator = CalcJobNode(computer=computer, process_type=entry_point)
            creator.set_option('resources', {'num_machines': 1, 'num_mpiprocs_per_machine': 1})
            #creator.set_attribute('prefix', 'aiida')
            remote.add_incoming(creator, link_type=LinkType.CREATE, link_label='remote_folder')
            creator.store()

        return remote

    return _generate_remote_data

@pytest.fixture
def generate_workchain():
    """Generate an instance of a `WorkChain`."""

    def _generate_workchain(entry_point, inputs):
        """Generate an instance of a `WorkChain` with the given entry point and inputs.
        :param entry_point: entry point name of the work chain subclass.
        :param inputs: inputs to be passed to process construction.
        :return: a `WorkChain` instance.
        """
        from aiida.engine.utils import instantiate_process
        from aiida.manage.manager import get_manager
        from aiida.plugins import WorkflowFactory

        process_class = WorkflowFactory(entry_point)
        runner = get_manager().get_runner()
        process = instantiate_process(runner, process_class, **inputs)

        return process

    return _generate_workchain


@pytest.fixture
def generate_wc_job_node():
    """Fixture to generate a mock `CalcJobNode` for testing parsers."""

    def flatten_inputs(inputs, prefix=''):
        """Flatten inputs recursively like :meth:`aiida.engine.processes.process::Process._flatten_inputs`."""
        flat_inputs = []
        for key, value in six.iteritems(inputs):
            if isinstance(value, collections.abc.Mapping):
                flat_inputs.extend(flatten_inputs(value, prefix=prefix + key + '__'))
            else:
                flat_inputs.append((prefix + key, value))
        return flat_inputs

    def _generate_wc_job_node(entry_point_name, computer, inputs=None):
        """Fixture to generate a mock `WorkChainNode` for testing parsers.
        :param entry_point_name: entry point name of the workchain class
        :param computer: a `Computer` instance
        :param inputs: any optional nodes to add as input links to the corrent CalcJobNode
        :return: `WorkChainNode` instance attached inputs if `inputs` is defined
        """
        from aiida import orm
        from aiida.common import LinkType
        from aiida.plugins.entry_point import format_entry_point_string

        entry_point = format_entry_point_string('aiida.workflows', entry_point_name)

        node = orm.WorkChainNode(computer=computer, process_type=entry_point)
        
        if inputs:
            for link_label, input_node in flatten_inputs(inputs):
                input_node.store()
                node.add_incoming(input_node, link_type=LinkType.INPUT_WORK, link_label=link_label)

        node.store()

        return node

    return _generate_wc_job_node
