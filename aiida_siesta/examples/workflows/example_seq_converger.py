#!/usr/bin/env runaiida

'''
This is an example of how to converge multiple parameters sequentially using the aiida_siesta
plugin.

It can be used for any parameter that the SiestaIterator understands. That is: fdf flags (including
the ones related to the basis), input keys of the SiestaBaseWorkChain or additional key parameters that
process the inputs for you to perform more complex input modifications. E.g: "kpoints_0", "kpoints_density"...
'''

# Not required by AiiDA
import os.path as op
import sys
import io

# AiiDA classes and functions
from aiida.engine import submit, run
from aiida.orm import load_code
from aiida.orm import Float, Dict, StructureData, Str, Int, KpointsData
from aiida_pseudo.data.pseudo.psf import PsfData
# The workchain that we are going to use to converge things.
from aiida_siesta.workflows.converge import SiestaSequentialConverger

'''
First of all, we need to setup all the inputs of the calculations.

See https://aiida-siesta-plugin.readthedocs.io/en/stable/workflows/base.html#inputs.

Basically, we will build an "inputs" dict at the end of the file, and all we are doing until
there is to build every part of it step by step.

All this is general to any SIESTA calculation with AiiDa, so if you already know how it works,
go to the end of the file, where we really do the convergence specific stuff.
'''

# Load the version of siesta that we are going to use
try:
    codename = sys.argv[1]
except IndexError:
    codename = 'Siesta-4.0.2@kay'
code = load_code(codename)

# Generate the structure (or get it from somewhere else)
try:
    # We can get it using sisl (useful if we have it in an *fdf, *XV, ...)
    import sisl
    
    ase_struct = sisl.geom.diamond(5.430, 'Si').toASE()
except:
    # Or using ASE
    import ase.build

    ase_struct = ase.build.bulk('Si', 'diamond', 5.430)
# Then just pass it to StructureData, which is the type that Aiida works with
structure = StructureData(ase=ase_struct)

# Specify some parameters that go into the fdf file
parameters = Dict(
    dict={
        'xc-functional': 'LDA',
        'xc-authors': 'CA',
        'max-scfiterations': 40,
        'dm-numberpulay': 4,
        'dm-mixingweight': 0.3,
        'dm-tolerance': 1.e-5,
        'Solution-method': 'diagon',
        'electronic-temperature': '25 meV',
    })

# Extra parameters that also go to the fdf file, but are related
# to the basis.
basis = Dict(
    dict={
        'pao-energy-shift': '300 meV',
        '%block pao-basis-sizes': """
Si DZP
%endblock pao-basis-sizes""",
    })

# Define the kpoints for the simulations. Note that this is not passed as
# a normal fdf parameter, it has "its own input"
kpoints = KpointsData()
kpoints.set_kpoints_mesh([14, 14, 14])

# Get the appropiate pseudos (in "real life", one could have a pseudos family defined
# in aiida database with `verdi data psf uploadfamily <path to folder> <family name>`)
# and then pass it as a simple string, Aiida will know which pseudos to use.
# See the pseudo_family in the aiida_siesta docs (link on top of the file)
pseudos_dict = {}
raw_pseudos = [("Si.psf", ['Si'])]
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

# Options that are related to how the job is technically submitted and
# run. Some of this options define flags for the job manager (e.g. SLURM)
# and some other's are related to how the code is executed. Note that 
# 'max_wallclock_seconds' is a required option, so that SIESTA can stop
# gracefully before the job runs out of time.
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

# Now we have all inputs defined, so as promised at the beggining of the file
# we build the inputs dicts to pass it to the process. There's no need though,
# we could pass each input separately. This is just so that the process call
# looks cleaner.
inputs = {
    'structure': structure,
    'parameters': parameters,
    'code': code,
    'basis': basis,
    'kpoints': kpoints,
    'pseudos': pseudos_dict,
    'options': options,
}

# Up until this point, all the things done have been general to any SIESTA
# simulation. Now, we will use the SiestaConverger to converge the mesh cutoff
# and the pao-energyshift simultaneously, meaning increasing both at the same time.
process = submit(SiestaSequentialConverger,
    iterate_over=[
        # First we want to converge the kpoints by increasing all components
        # at the same time.
        {
            'kpoints_0': [4,10,12,14,16,18,20],
            'kpoints_1': [4,10,12,14,16,18,20],
            'kpoints_2': [4,10,12,14,16,18,20],
        },
        # Then the mesh cutoff (using the default units, Ry)
        {
            'meshcutoff': [500, 600, 700,
                            800, 900, 1000],
        },
        # And finally the energy shift (using the default units, Ry)
        {
            'pao-energyshift': [0.02, 0.015, 0.01, 0.005, 0.001]
        },
        # Note that we can converge the same parameters again if we wanted,
        # so we could do another round of k point convergence here.
    ],
    # And now we are passing the inputs for the converger:
    converger_inputs={
        # All the general inputs for the siesta simulation
        **inputs,
        # These are the defaults target and threshold, but we are going
        # to pass them here to make it clear that this can be tuned.
        "target": Str('E_KS'),
        "threshold": Float(0.01),
        # And we also specify a batch size to submit more than one job at a time
        "batch_size": Int(1)
    }
    
)
# Print some info
print("Submitted workchain; ID={}".format(process.pk))
print(
    "For information about this workchain type: verdi process show {}".format(
        process.pk))
print("For a list of running processes type: verdi process list")
