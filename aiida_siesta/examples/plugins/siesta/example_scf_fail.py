#!/usr/bin/env runaiida
# This is an example of a calculation that will end in a FINISHED
# state but with a non-zero exit code, due to lack of scf convergence
# in the allotted number of iterations.

import sys
import os.path as op
import io

from aiida.engine import submit
from aiida.orm import load_code
from aiida_siesta.calculations.siesta import SiestaCalculation
from aiida.plugins import DataFactory

################################################################

PsfData = DataFactory('pseudo.psf')
KpointsData = DataFactory('array.kpoints')
StructureData = DataFactory('structure')
Dict = DataFactory('dict')

try:
    dontsend = sys.argv[1]
    if dontsend == "--dont-send":
        submit_test = True
    elif dontsend == "--send":
        submit_test = False
    else:
        raise IndexError
except IndexError:
    print(("The first parameter can only be either "
           "--send or --dont-send"),
          file=sys.stderr)
    sys.exit(1)

try:
    codename = sys.argv[2]
except IndexError:
    codename = 'Siesta4.0.1@kelvin'

#
#------------------Code
#
code = load_code(codename)

#--------------- Structure
#
#    Bulk Silicon
#
alat = 5.430  # angstrom
cell = [
    [
        0.5 * alat,
        0.5 * alat,
        0.,
    ],
    [
        0.,
        0.5 * alat,
        0.5 * alat,
    ],
    [
        0.5 * alat,
        0.,
        0.5 * alat,
    ],
]

s = StructureData(cell=cell)
s.append_atom(position=(0.000 * alat, 0.000 * alat, 0.000 * alat),
              symbols=['Si'])
s.append_atom(position=(0.250 * alat, 0.250 * alat, 0.250 * alat),
              symbols=['Si'])

#----------------------------------------------

options = {
#    "queue_name": "debug",
    "max_wallclock_seconds": 1700,
    "resources": {
        "num_machines": 1,
        "num_mpiprocs_per_machine": 1,
    }
}

#-------------------------- Settings ---------------------------------
#
settings_dict = {'additional_retrieve_list': ['aiida.BONDS', 'aiida.EIG']}
settings = Dict(dict=settings_dict)

#---------------------------------------------
# Code-specific operational parameters
#
params_dict = {
    'xc-functional': 'LDA',
    'xc-authors': 'CA',
    'spin-polarized': True,
    'meshcutoff': '40.000 Ry',
    'dm-numberpulay': 4,
    'dm-mixingweight': 0.3,
    'dm-tolerance': 1.e-3,
    'max-scfiterations': 3,
    'scf-must-converge': True,
    'md-typeofrun': 'cg',
    'md-numcgsteps': 0
}

parameters = Dict(dict=params_dict)

# ---------------------Basis Set Info -----------------------------------
# The basis dictionary follows the 'parameters' convention
#
basis_dict = {
    'pao-energy-shift':
    '300 meV',
    '%block pao-basis-sizes':
    """
Si DZP                    
%endblock pao-basis-sizes""",
}

basis = Dict(dict=basis_dict)

#-------------------------------------------
kpoints = KpointsData()

# method mesh
kpoints_mesh = 4
kpoints.set_kpoints_mesh([kpoints_mesh, kpoints_mesh, kpoints_mesh])

#------------------------------------------------
pseudos_dict = {}
raw_pseudos = [("Si.psf", ['Si'])]
for fname, kinds in raw_pseudos:
    absname = op.realpath(op.join(op.dirname(__file__), "../../fixtures/sample_psf", fname))
    with io.open(absname, 'rb') as handle:
        pseudo = PsfData.get_or_create(handle)
    if not pseudo.is_stored:
        print("\nCreated the pseudo for {}".format(kinds))
    else:
        print("\nUsing the pseudo for {} from DB: {}".format(kinds, pseudo.pk))
    for j in kinds:
        pseudos_dict[j]=pseudo

#---------------------------------------------

inputs = {
    'structure': s,
    'parameters': parameters,
    'code': code,
    'basis': basis,
    'kpoints': kpoints,
    'pseudos': pseudos_dict,
    'metadata': {
        'options': options,
        'label': "Bulk Si short scf cycle"
    }
}

if submit_test:
    inputs["metadata"]["dry_run"] = True
    inputs["metadata"]["store_provenance"] = False
    process = submit(SiestaCalculation, **inputs)
    print("Submited test for calculation (uuid='{}')".format(process.uuid))
    print("Check the folder submit_test for the result of the test")

else:
    process = submit(SiestaCalculation, **inputs)
    print("Submitted calculation; ID={}".format(process.pk))
    print("For information about this calculation type: verdi process show {}".
          format(process.pk))
    print("For a list of running processes type: verdi process list")
