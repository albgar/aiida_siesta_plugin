#!/usr/bin/env runaiida

#Not required by AiiDA
import os.path as op
import sys

#AiiDA classes and functions
from aiida.engine import submit
from aiida.orm import load_code
from aiida.orm import (Dict, StructureData, KpointsData, Str)
from aiida_siesta.workflows.base import SiestaBaseWorkChain

# This example shows the use of the SiestaBaseWorkChain
# Requires a working aiida profile and the set up of
# a code (it submits the WorkChain to the daemon).
# To run it: runaiida example_first.py codename
# The inputs are the same of ../plugins/siesta/example_first.py
# However max-scfiterations' is set to 4. The calculation
# does not converge in 4 iterations, but the WorkChain
# automatically recognises the error and takes care of
# resubmitting the calculation.

try:
    codename = sys.argv[1]
except IndexError:
    codename = 'Siesta-4.0.2@kay'

#The code
code = load_code(codename)

#The structure. Si diamond structure
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
#The atom positions were originally given in the "ScaledCartesian" format
#but standard for aiida structures is Cartesian in Angstrom
structure = StructureData(cell=cell)
structure.append_atom(position=(0.000 * alat, 0.000 * alat, 0.000 * alat),
                      symbols=['Si'])
structure.append_atom(position=(0.250 * alat, 0.250 * alat, 0.250 * alat),
                      symbols=['Si'])

#The parameters
parameters = Dict(
    dict={
        'xc-functional': 'LDA',
        'xc-authors': 'CA',
        'max-scfiterations': 4,
        'dm-numberpulay': 4,
        'dm-mixingweight': 0.3,
        'dm-tolerance': 1.e-5,
        'Solution-method': 'diagon',
        'electronic-temperature': '25 meV',
        'write-forces': True,
    })

#The basis set
basis = Dict(dict={
    'floating_sites': [{"name":'Si_bond', "symbols":'Si', "position":(0.125*alat, 0.125*alat, 0.125*alat)}],
    'pao-energy-shift': '300 meV',
    '%block pao-basis-sizes': "\n Si DZP\n%endblock pao-basis-sizes",
    })

#The kpoints
kpoints = KpointsData()
kpoints.set_kpoints_mesh([4, 4, 4])

#Resources
options = Dict(
    dict={
        "max_wallclock_seconds": 360,
        #'withmpi': True,
        #'account': "tcphy113c",
        #'queue_name': "DevQ",
        "resources": {
            "num_machines": 1,
            "num_mpiprocs_per_machine": 1,
        }
    })

#The submission
#All the inputs of a Siesta calculations are listed in a dictionary
#Note the different use of options compared to ../plugins/siesta/example_first.py
inputs = {
    'structure': structure,
    'parameters': parameters,
    'code': code,
    'basis': basis,
    'kpoints': kpoints,
    'pseudo_family': Str("PseudoDojo/0.4/PBE/SR/standard/psml"),
    'options': options
}

process = submit(SiestaBaseWorkChain, **inputs)
print("Submitted workchain; ID={}".format(process.pk))
print(
    "For information about this workchain type: verdi process show {}".format(
        process.pk))
print("For a list of running processes type: verdi process list")
