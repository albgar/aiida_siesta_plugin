#!/usr/bin/env runaiida

import sys
import os.path as op
import io
import numpy as np
from aiida.engine import submit
from aiida.orm import load_code
from aiida_siesta.calculations.siesta import SiestaCalculation
from aiida.plugins import DataFactory
from aiida_siesta.workflows.stm import SiestaSTMWorkChain

# This is an example for the submission of the STM WorkChain
# in order to obtain spin dependent stm images
# For a quick run, type:
# "runaiida example_stm_magn.py SiestaCode@cmp StmCoode@cmp"
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
    "max_wallclock_seconds": 33360,
    'withmpi': True,
    #'account': "tcphy113c",
    #'queue_name': "DevQ",
    "resources": {
        "num_machines": 1,
        "num_mpiprocs_per_machine": 4,
    }
}
#
# Structure, a Cr slab
#
struct_params = {'numbers': np.array([24, 24, 24]),
 'positions': np.array([[ 7.800000e-05, -4.700000e-05, -2.434600e-02],
        [ 1.630000e-04,  3.335886e+00,  7.413000e-02],
        [ 2.889124e+00,  1.667948e+00, -4.978400e-02]]),
 'masses': np.array([51.9961, 51.9961, 51.9961]),
 'cell': np.array([[ 5.77810000e+00,  0.00000000e+00,  3.53806584e-16],
        [-2.88905000e+00,  5.00398139e+00,  3.53806584e-16],
        [ 0.00000000e+00,  0.00000000e+00,  2.17943981e+01]]),
 'pbc': np.array([ True,  True,  True])}

import ase.atoms

truct = ase.atoms.Atoms().fromdict(struct_params)

s = StructureData(ase=truct)
#
# Parameters ---------------------------------------------------
#
params_dict = {
    'MeshCutoff': "1200. Ry",
    'spin':'spin-orbit',
    'md-maxcgdispl': '0.1 Ang',
    'md-maxforcetol': '0.04 eV/Ang',
    'write-forces': True,
    'xc-functional': 'GGA',
    'xc-authors': 'PW91',
    'dm-numberpulay': 8,
    'dm-mixingweight': 0.004,
    'dm-tolerance': 1.e-4,
    'electronic-temperature': '300.000 K',
    '%block DMInitSpin':
     """
     1 +3.73  90.0  60.0
     2 +3.73  90.0 -60.0
     3 +3.73  90.0 180.0\n%endblock DMInitSpin"""
}
parameters = Dict(dict=params_dict)
#
# Kpoints
#
kpoints = KpointsData()
kpoints.set_kpoints_mesh([15, 15, 1])
#
# Basis Set Info ------------------------------------------
# The basis dictionary follows the 'parameters' convention
#
basis_dict = {
    'pao-basistype':'split',
    'pao-splitnorm': 0.150,
    'pao-energyshift':'0.020 Ry',
    '%Block PAO-Basis':
    """
    Cr   3
    n=4   0   2
	0.0   0.0
    n=4   1   2
	0.0   0.0
    n=3   2   2
	0.0   0.0\n%endblock PAO.Basis"""
}
basis = Dict(dict=basis_dict)
#--------------------------------------------------------------

#--------------------- Pseudopotentials ---------------------------------
#
# This exemplifies the handling of pseudos for different species
# Those sharing the same pseudo should be indicated.
#
pseudos_dict = {}
raw_pseudos = [("Cr.psf", ['Cr'])]
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
    'kpoints': kpoints,
    'options': Dict(dict=options),
    'emin': Float(-1),
    'emax': Float(+0.1),
    'stm_code': stm_code,
    'stm_mode': Str("constant-height"),
    'stm_value': Float(3.0),
    'stm_spin': Str("non-collinear")
    }

process = submit(SiestaSTMWorkChain, **inputs)
print("Submitted workchain; ID={}".format(process.pk))
print(
    "For information about this workchain type: verdi process show {}".format(
        process.pk))
print("For a list of running processes type: verdi process list")

