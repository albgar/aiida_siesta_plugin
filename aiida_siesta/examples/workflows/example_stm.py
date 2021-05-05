import sys
import os.path as op
import io
from aiida.engine import submit
from aiida.orm import load_code
from aiida_siesta.calculations.siesta import SiestaCalculation
from aiida.plugins import DataFactory
from aiida_siesta.workflows.stm import SiestaSTMWorkChain

# This is an example for the submission of the STM WorkChain.
# It shows how to select all the inputs of the WorkChain
# and how to submit it.
# For a quick run, type:
# "runaiida example_stm.py SiestaCode@cmp StmCoode@cmp"
# but, as any other example here, it is made to make the user
# play with all the inputs of the WorkChain


PsfData = DataFactory('pseudo.psf')
Dict = DataFactory('dict')
KpointsData = DataFactory('array.kpoints')
StructureData = DataFactory('structure')


try:
    codename = sys.argv[1]
except IndexError:
    codename = 'SiestaHere@localhost'
try:
    stm_codename = sys.argv[2]
except IndexError:
    stm_codename = 'STMhere@localhost'

#
#------------------Code and computer options ---------------------------
#
code = load_code(codename)
stm_code = load_code(stm_codename)

options = {
    "max_wallclock_seconds": 360,
    #'withmpi': True,
    #'account': "tcphy113c",
    #'queue_name': "DevQ",
    "resources": {
        "num_machines": 1,
        "num_mpiprocs_per_machine": 1,
    }
}

#
# Structure -----------------------------------------
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

# Benzene molecule
# Note an atom tagged (for convenience) with a different label
#
s = StructureData(cell=cell)
s.append_atom(position=(0.468, 0.000, 0.000), symbols=['H'])
s.append_atom(position=(1.620, 0.000, 0.000), symbols=['C'])
s.append_atom(position=(1.754, -2.233, 0.000), symbols=['H'])
s.append_atom(position=(1.754, 2.233, 0.000), symbols=['H'])
s.append_atom(position=(2.327, -1.225, 0.000), symbols='C', name="Cred")
s.append_atom(position=(2.327, 1.225, 0.000), symbols=['C'])
s.append_atom(position=(3.737, -1.225, 0.000), symbols=['C'])
s.append_atom(position=(3.737, 1.225, 0.000), symbols=['C'])
s.append_atom(position=(4.311, -2.233, 0.000), symbols=['H'])
s.append_atom(position=(4.311, 2.233, 0.000), symbols=['H'])
s.append_atom(position=(4.442, 0.000, 0.000), symbols=['C'])
s.append_atom(position=(5.604, 0.000, 0.000), symbols=['H'])

#-------------------------------------------------------------
#
# Parameters ---------------------------------------------------
#
params_dict = {
    'spin':'spin-orbit',
    'md-typeofrun': 'cg',
    'md-numcgsteps': 10,
    'md-maxcgdispl': '0.1 Ang',
    'md-maxforcetol': '0.04 eV/Ang',
    'write-forces': True,
    'xc-functional': 'LDA',
    'xc-authors': 'CA',
    'mesh-cutoff': '250.000 Ry',
    'dm-numberpulay': 5,
    'dm-mixingweight': 0.050,
    'dm-tolerance': 1.e-4,
    'electronic-temperature': '100.000 K',
    '%block local-density-of-states':
    """
 -9.6 -1.6 eV
%endblock local-density-of-states """
}
parameters = Dict(dict=params_dict)
#
# Basis Set Info ------------------------------------------
# The basis dictionary follows the 'parameters' convention
#
basis_dict = {
    'pao-basistype':'split',
    'pao-splitnorm': 0.150,
    'pao-energyshift':'0.020 Ry',
    '%block pao-basis-sizes':
    """
C    SZP
Cred SZ
H    SZP
%endblock pao-basis-sizes"""
}
basis = Dict(dict=basis_dict)
#--------------------------------------------------------------

#--------------------- Pseudopotentials ---------------------------------
#
# This exemplifies the handling of pseudos for different species
# Those sharing the same pseudo should be indicated.
#
pseudos_dict = {}
raw_pseudos = [("C.psf", ['C', 'Cred']), ("H.psf", ['H'])]
for fname, kinds in raw_pseudos:
    absname = op.realpath(op.join(op.dirname(__file__), "../fixtures/sample_psf", fname))
    with io.open(absname, 'rb') as handle:
        pseudo = PsfData.get_or_create(handle)
    if not pseudo.is_stored:
        print("\nCreated the pseudo for {}".format(kinds))
    else:
        print("\nUsing the pseudo for {} from DB: {}".format(kinds, pseudo.pk))
    for j in kinds:
        pseudos_dict[j]=pseudo


#-----------------------------------------------------------------------
#--All the inputs of a Siesta calculations are listed in a dictionary--
#
inputs = {
    'structure': s,
    'parameters': parameters,
    'code': code,
    'basis': basis,
    'pseudos': pseudos_dict,
    'options': Dict(dict=options),
    'emin': Float(-6.5),
    'emax': Float(0.0),
    'stm_code': stm_code,
    'stm_mode': Str("constant-height"),
    'stm_value': Float(1.6),
    'stm_spin': Str("none")
    }

process = submit(SiestaSTMWorkChain, **inputs)
print("Submitted workchain; ID={}".format(process.pk))
print(
    "For information about this workchain type: verdi process show {}".format(
        process.pk))
print("For a list of running processes type: verdi process list")

