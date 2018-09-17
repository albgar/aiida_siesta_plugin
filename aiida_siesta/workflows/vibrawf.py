# -*- coding: utf-8 -*-
from aiida.orm import Code
from aiida.orm.data.base import Bool, Int, Str, Float
from aiida.orm.data.parameter import ParameterData
from aiida.orm.data.structure import StructureData
from aiida.orm.data.array.kpoints import KpointsData
from aiida.orm.data.array import ArrayData
from aiida.orm.data.remote import RemoteData

from aiida.work.run import submit
from aiida.work.workchain import WorkChain, ToContext
from aiida.work.workfunction import workfunction
from aiida.common.links import LinkType

from aiida_siesta.data.psf import get_pseudos_from_structure

from aiida_siesta.workflows.base import SiestaBaseWorkChain
from aiida_siesta.calculations.vibra import VibraCalculation

from buildsc import buildsc

__copyright__ = u"Copyright (c), 2015, ECOLE POLYTECHNIQUE FEDERALE DE LAUSANNE (Theory and Simulation of Materials (THEOS) and National Centre for Computational Design and Discovery of Novel Materials (NCCR MARVEL)), Switzerland and ROBERT BOSCH LLC, USA. All rights reserved."
__license__ = "MIT license, see LICENSE.txt file"
__version__ = "0.12.0"
__contributors__ = "Victor M. Garcia-Suarez, ..."
                        
class SiestaVibraWorkChain(WorkChain):
    """
    Vibra Workchain. An example of workflow composition for phonons
    """

    def __init__(self, *args, **kwargs):
        super(SiestaVibraWorkChain, self).__init__(*args, **kwargs)

    @classmethod
    def define(cls, spec):
        super(SiestaVibraWorkChain, cls).define(spec)
        spec.input('code', valid_type=Code)
        spec.input('vibra_code', valid_type=Code)
        spec.input('scarray', valid_type=ArrayData)
        spec.input('structure', valid_type=StructureData)
        spec.input('protocol', valid_type=Str, default=Str('standard'))
        spec.input('bandskpoints', valid_type=KpointsData)
        spec.outline(
            cls.setup_structures,
            cls.setup_rsi_inputs,
            cls.setup_protocol,
            cls.setup_pseudo_potentials,
            cls.setup_siesta_parameters,
            cls.setup_basis,
            cls.setup_kpoints,
            cls.run_siesta,
            cls.run_vibra,
            cls.run_results,
        )
        spec.dynamic_output()
                                         
    def setup_structures(self):
        """
        Very simple. Avoid seekpath for now
        """
        self.report('Running setup_structure')

        self.ctx.structure_initial_primitive = self.inputs.structure
        scell, xasc, specsc = buildsc(self.inputs.scarray,self.inputs.structure)
        nna=len(xasc)
        self.ctx.structure_supercell = StructureData(cell=scell)
        for i in range(nna):
            self.ctx.structure_supercell.append_atom(position=(xasc[i][0],\
                    xasc[i][1],xasc[i][2]),symbols=specsc[i])

    def setup_rsi_inputs(self):
        """
        Setup of context variables and inputs for the SiestaBaseWorkChain. Based on the specified
        protocol, we define values for variables that affect the execution of the calculations
        """
        self.ctx.rsi_inputs = {
            'code': self.inputs.code,
            'parameters': {},
            'settings': {},
            'options': ParameterData(dict={
                'resources': {
                    'parallel_env': 'mpi',
                    'tot_num_mpiprocs':1
                },
                'max_wallclock_seconds': 1800,
            }),
        }

    def setup_protocol(self):
        if self.inputs.protocol == 'standard':
            self.report('running the workchain in the "{}" protocol'.format(self.inputs.protocol.value))
            self.ctx.protocol = {
                'kpoints_mesh': 1,
                'dm_convergence_threshold': 1.0e-4,
                'min_meshcutoff': 100, # In Rydberg (!)
                'electronic_temperature': "25.0 meV",
                'pseudo_familyname': 'si_ldapsf',
                'atomic_heuristics': {
                    'Si': { 'cutoff': 100 }
                },
                'basis': {
                    'pao-energy-shift': '100 meV',
                    'pao-basis-size': 'DZP'
                }
                          
            }
        elif self.inputs.protocol == 'fast':
            self.report('running the workchain in the "{}" protocol'.format(self.inputs.protocol.value))
            self.ctx.protocol = {
                'kpoints_mesh': 1,
                'dm_convergence_threshold': 1.0e-3,
                'min_meshcutoff': 80, # In Rydberg (!)
                'electronic_temperature': "25.0 meV",
                'pseudo_familyname': 'si_ldapsf',
                'atomic_heuristics': {
                    'Si': { 'cutoff': 50 }
                },
                'basis': {
                    'pao-energy-shift': '100 meV',
                    'pao-basis-size': 'SZ'
                }
                          
            }
        else:
            self.abort_nowait('Protocol {} not known'.format(self.ctx.protocol.value))

    def setup_pseudo_potentials(self):
        """
        Based on the given input structure, get the 
        pseudo potentials for the different elements in the structure
        """
        self.report('Running setup_pseudo_potentials')
        structure = self.ctx.structure_initial_primitive
        pseudo_familyname = self.ctx.protocol['pseudo_familyname']
        self.ctx.rsi_inputs['pseudos'] = get_pseudos_from_structure(structure, pseudo_familyname)

    def setup_siesta_parameters(self):
        """
        Setup the default input parameters required for a
        SiestaCalculation and the SiestaBaseWorkChain
        """

        self.report('Running setup_siesta_parameters')
        structure = self.ctx.structure_initial_primitive
        meshcutoff = 0.0

        for kind in structure.get_kind_names():
            try:
                cutoff = self.ctx.protocol['atom_heuristics'][kind]['cutoff']
                meshcutoff = max(meshcutoff,cutoff)
            except:
                pass    # No problem. No heuristics, no info

        # In case we did not get anything, set a minimum value
        meshcutoff = max(self.ctx.protocol['min_meshcutoff'], meshcutoff)    
                
        self.ctx.rsi_inputs['parameters'] = {
            'dm-tolerance': self.ctx.protocol['dm_convergence_threshold'],
            'mesh-cutoff': "{} Ry".format(meshcutoff),
            'electronic-temperature': self.ctx.protocol['electronic_temperature'],
            # Parameters for the FC run
            'md-typeofrun': 'FC',
            'md-fcfirst': 27,
            'md-fclast': 28,
            'md-fcdispl': '0.0211672 Ang'
        }

    def setup_basis(self):
        """
        Setup the basis dictionary.
        Very simple for now. Just the same for all elements. With more heuristics, we could do more.
        """
        self.report('Running setup_basis')
        self.ctx.rsi_inputs['basis'] = self.ctx.protocol['basis']
        
    def setup_kpoints(self):
        """
        Define the k-point mesh for the Siesta calculation.
        """
        self.report('Running setup_kpoints')
        kpoints_mesh = KpointsData()
        kpmesh=self.ctx.protocol['kpoints_mesh']
        kpoints_mesh.set_kpoints_mesh([kpmesh,kpmesh,kpmesh])
        
        self.ctx.kpoints_mesh = kpoints_mesh

    def run_siesta(self):
        """
        Run the SiestaBaseWorkChain to calculate the input structure
        """
        self.report('Running run_siesta')

        rsi_inputs = {}
        rsi_inputs = dict(self.ctx.rsi_inputs)

        # Get the remote folder of the last calculation in the previous workchain

        rsi_inputs['kpoints'] = self.ctx.kpoints_mesh
        rsi_inputs['basis'] = ParameterData(dict=rsi_inputs['basis'])
        rsi_inputs['structure'] = self.ctx.structure_supercell
        rsi_inputs['parameters'] = ParameterData(dict=rsi_inputs['parameters'])
        rsi_inputs['settings'] = ParameterData(dict=rsi_inputs['settings'])
        rsi_inputs['clean_workdir'] = Bool(False)
        rsi_inputs['max_iterations'] = Int(20)
        
        running = submit(SiestaBaseWorkChain, **rsi_inputs)
        self.report('launched SiestaBaseWorkChain<{}> in run-Siesta mode'.format(running.pid))
        
        return ToContext(workchain_siesta=running)

    def run_vibra(self):
        """
        Run a VibraCalculation with the calculation parent folder
        """
        self.report('Running vibra calculation')
        # Get the remote folder of the last calculation in the previous workchain
        remote_folder = self.ctx.workchain_siesta.get_outputs_dict()['remote_folder']

        vibra_inputs = {}
        vibra_inputs['code'] = self.inputs.vibra_code
        vibra_inputs['parent_folder'] = remote_folder
        vibra_inputs['structure'] = self.inputs.structure
        vibra_inputs['bandskpoints'] = self.inputs.bandskpoints

        vibra_settings_dict = {}
        vibra_inputs['settings'] = ParameterData(dict=vibra_settings_dict)

        vibra_parameters_dict = {
                'atomicdispl':  '0.0211672 Ang',
                'eigenvectors': True
        }
        vibra_inputs['parameters'] = ParameterData(dict=vibra_parameters_dict)

        vibra_inputs['_options'] = {
            'resources': {
                'parallel_env': 'mpi',
                'tot_num_mpiprocs':1
            },
            'max_wallclock_seconds': 600
        }

        process = VibraCalculation.process()
        running = submit(process, **vibra_inputs)
        
        self.report('launching VibraCalculation<{}>'.format(running.pid))
        
        return ToContext(vibra_calc=running)

    def run_results(self):
        """
        Attach the relevant output nodes from the vibra calculation to the workchain outputs
        for convenience
        """
        calculation_vibra = self.ctx.vibra_calc

        self.report('workchain succesfully completed'.format())
