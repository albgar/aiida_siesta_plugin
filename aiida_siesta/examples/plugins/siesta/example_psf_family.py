#!/usr/bin/env runaiida

import sys

from aiida.engine import submit
from aiida.orm import load_code
from aiida_siesta.calculations.siesta import SiestaCalculation
from aiida.plugins import DataFactory

#----------------- Example of the use of a pseudopotential family
# Read 00_README to learn how to set up a family

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
settings_dict = {'additional_retrieve_list': ['aiida.BONDS', 'aiida.EIG']}
settings = Dict(dict=settings_dict)
#---------------------------------------------------------------------

#
#-------------------------- Structure --------------------------------
#
alat = 15.  # angstrom
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

# Note an atom tagged (for convenience) with a different label

s = StructureData(cell=cell)
s.append_atom(position=(0.000, 0.000, 0.468), symbols=['H'])
s.append_atom(position=(0.000, 0.000, 1.620), symbols=['C'])
s.append_atom(position=(0.000, -2.233, 1.754), symbols=['H'])
s.append_atom(position=(0.000, 2.233, 1.754), symbols=['H'])
s.append_atom(position=(0.000, -1.225, 2.327), symbols='C', name="Cred")
s.append_atom(position=(0.000, 1.225, 2.327), symbols=['C'])
s.append_atom(position=(0.000, -1.225, 3.737), symbols=['C'])
s.append_atom(position=(0.000, 1.225, 3.737), symbols=['C'])
s.append_atom(position=(0.000, -2.233, 4.311), symbols=['H'])
s.append_atom(position=(0.000, 2.233, 4.311), symbols=['H'])
s.append_atom(position=(0.000, 0.000, 4.442), symbols=['C'])
s.append_atom(position=(0.000, 0.000, 5.604), symbols=['H'])

#-----------------------------------------------------------------------

#
# ----------------------Parameters -------------------------------------
#
params_dict = {
    'xc-functional': 'LDA',
    'xc-authors': 'CA',
    'mesh-cutoff': '200.000 Ry',
    'max-scfiterations': 1000,
    'dm-numberpulay': 5,
    'dm-mixingweight': 0.050,
    'dm-tolerance': 1.e-4,
    'dm-mixscf1': True,
    'negl-nonoverlap-int': False,
    'solution-method': 'diagon',
    'electronic-temperature': '100.000 K',
    'writeforces': True,
}

parameters = Dict(dict=params_dict)
#------------------------------------------------------------------------

#
# ---------------------Basis Set Info -----------------------------------
# The basis dictionary follows the 'parameters' convention
#
basis_dict = {
    'pao-basistype':
    'split',
    'pao-splitnorm':
    0.150,
    'pao-energyshift':
    '0.020 Ry',
    '%block pao-basis-sizes':
    """
C    SZP
Cred SZ
H    SZP
%endblock pao-basis-sizes""",
}

basis = Dict(dict=basis_dict)
#------------------------------------------------------------------------

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
    'basis': basis,
    'pseudos': pseudos_dict,
    'metadata': {
        'options': options,
        'label': "Benzene molecule with pseudo family",
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
