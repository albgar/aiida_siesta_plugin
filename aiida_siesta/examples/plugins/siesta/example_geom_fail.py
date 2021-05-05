#!/usr/bin/env runaiida
import sys

from aiida.engine import submit
from aiida.orm import load_code, Group
from aiida_siesta.calculations.siesta import SiestaCalculation
from aiida.plugins import DataFactory

#  Siesta calculation on Water molecule -- to fail in geom relaxation

PsfData = DataFactory('siesta.psf')
Dict = DataFactory('dict')
KpointsData = DataFactory('array.kpoints')
StructureData = DataFactory('structure')

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
#
try:
    codename = sys.argv[2]
except IndexError:
    codename = 'Siesta4.0.1@kelvin'

#
#------------------Code and computer options ---------------------------
#
code = load_code(codename)

options = {
#    "queue_name": "debug",
    "max_wallclock_seconds": 1700,
    "resources": {
        "num_machines": 1,
        "num_mpiprocs_per_machine": 1,
    }
}
#
#-------------------------- Settings ---------------------------------
#
settings_dict = {'additional_retrieve_list': ['aiida.BONDS', 'aiida.EIG']}
settings = Dict(dict=settings_dict)
#
# Structure -----------------------------------------
#
alat = 10.0  # angstrom
cell = [
    [
        alat,
        0.,
        0.,
    ],
    [
        0.,
        alat,
        0.,
    ],
    [
        0.,
        0.,
        alat,
    ],
]

# Water molecule
# One of the H atoms is sligthy moved

s = StructureData(cell=cell)
s.append_atom(position=(0.000, 0.000, 0.00), symbols=['O'])
s.append_atom(position=(0.757, 0.586, 0.00), symbols=['H'])
s.append_atom(position=(-0.780, 0.600, 0.00), symbols=['H'])

# ----------------------Parameters -------------------------------------

params_dict = {
    'xc-functional': 'LDA',
    'xc-authors': 'CA',
    'mesh-cutoff': '100.000 Ry',
    'max-scfiterations': 30,
    'dm-numberpulay': 4,
    'dm-mixingweight': 0.1,
    'dm-tolerance': 1.e-4,
    'md-typeofrun': 'cg',
    'md-numcgsteps': 7,
    'md-maxcgdispl': '0.200 bohr',
    'md-maxforcetol': '0.020 eV/Ang',
}

parameters = Dict(dict=params_dict)
#------------------------------------------------------------------------
#
# No basis set spec in this calculation (default)
#
#--------------------- Pseudopotentials ---------------------------------
#
# FIXME: The family name is hardwired
#
family = Group.get(label='psf_family')
pseudos_dict = family.get_pseudos(structure=s)
#-----------------------------------------------------------------------

#
#--All the inputs of a Siesta calculations are listed in a dictionary--
#
inputs = {
    'structure': s,
    'parameters': parameters,
    'code': code,
    'pseudos': pseudos_dict,
    'metadata': {
        'options': options,
        'label': "Water molecule -- geom fail"
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
