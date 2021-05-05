Base workflow
+++++++++++++

Description
-----------

The SIESTA program is able to perform, in a single run, the
computation of the electronic structure, the optional relaxation of
the input structure, and a final analysis step in which a variety of
magnitudes can be computed: band structures, projected densities of
states, etc. The operations to be carried out are specified in a very
flexible input format.  Accordingly, the **SiestaBaseWorkChain**
has been designed to be able to run the most general SIESTA
calculation, with support for most of the available options (limited
only by corresponding support in the parser plugin). The option specifications
of the **SiestaBaseWorkChain** follow the conventions already presented in the
:ref:`Siesta plugin <siesta-plugin-inputs>`. Therefore, for instance, the addition of
the input keyword **bandskpoints** triggers the calculation of the band structure
of a system, while it is sufficient to add the SIESTA MD keywords to the
**parameters** input in order to perforem the relaxation of a structure.
In contarst to the **SiestaCalculation** plugin, however, the 
workchain is able to automatically restart a calculation in case of failure (lack of
electronic-structure or geometry relaxation convergence, termination due to
walltime restrictions, etc).
Therefore, the **SiestaBaseWorkChain** is the suggested tool to run Siesta calculations
in the AiiDA framework. In fact, it retains the same level of flexibility of the most
general Siesta calculation, but it adds robusness thanks to its ability
to automatically respond to erros.
Examples on the use of the **SiestaBaseWorkChain** are presented in the folder
`/aiida_siesta/examples/workflows`.


Supported Siesta versions
-------------------------

At least 4.0.1 of the 4.0 series, 4.1-b3 of the 4.1 series and the MaX-1.0 release, which
can be found in the development platform
(https://gitlab.com/siesta-project/siesta).
For more up to date info on compatibility, please check the      
`wiki <https://github.com/siesta-project/aiida_siesta_plugin/wiki/Supported-siesta-versions>`_.



.. _siesta-base-wc-inputs:

Inputs
------

All the siesta plugin inputs are also inputs of the **SiestaBaseWorkChain**. Therefore,
detailed information on them can be found :ref:`here <siesta-plugin-inputs>`.
The only difference is regarding the way the computational resources are passed. 
The siesta plugin makes use of ``metadada.options`` for this task, here, instead, we have
a dedicated input node.

* **options**, class :py:class:`Dict <aiida.orm.Dict>`, *Mandatory*

  Execution options for the siesta calculation. In this dictionary the computational resources and
  scheduler specifications (queue, account, etc ..) must be specified.
  An example is::
        options = Dict(
             dict={
                'max_wallclock_seconds': 360,
                'withmpi': True,
                'account': 'tcphy113c',
                'queue_name': 'DevQ',
                'resources': {'num_machines': 1,'num_mpiprocs_per_machine': 2},
                }
             )

  The `resources` and `max_wallclock_seconds` are required by AiiDA, the rest of the options
  depend on the scheduler of the machine one is submitting to.


The **SiestaBaseWorkChain** also has some additional inputs that allow
to control additional features.

* **pseudo_family**, class :py:class:`Str <aiida.orm.Str>`, *Optional*

  String representing the name of a pseudopotential family stored in the database.
  Pseudofamilies can be installed in the database via the ``aiida-pseudo install family``
  CLI interface. As already specified in the description of the **pseudos** input
  :ref:`here <siesta-plugin-inputs>`.

.. |br| raw:: html

    <br />

* **clean_workdir**, class :py:class:`Bool <aiida.orm.Bool>`, *Optional*

  If true, work directories of all called calculations will be cleaned
  out. Default is false.

.. |br| raw:: html

    <br />

* **max_iterations**, class :py:class:`Int <aiida.orm.Int>`, *Optional*

  The maximum number of iterations allowed in the restart cycle for
  calculations. The **SiestaBaseWorkChain** tries to deal with some 
  common siesta errors (see `here <basewc-error>`) and restart the calculation with appropriate
  modifications. The integer **max_iterations** is the maximum number
  of times the restart is performed no matter what error is recorded.
  The input is optional, if not specified, the default `Int(5)` is used.

.. |br| raw:: html

    <br />


Relaxation and bands
--------------------
As already mentioned in the introduction, in addition to simple scf calculations, the **SiestaBaseWorkChain** 
can be used to perform the relaxation of a structure and the electronic bands calculations.
For the electronic bands, however, we suggest the use of the **BandgapWorkChain** distributed in this package, because
it adds the feature to automatically calculate the band gap.
Concerning the relaxation of a structure, the **SiestaBaseWorkChain** simply exploits the internal relaxation
implemented in Siesta in order to complete the task. The full set of a Siesta relaxation options can be
accessed just adding the corresponding keyword and value in the **parameters** input dictionary. The only additional
feature that the **SiestaBaseWorkChain** adds is that it requires to reach the target forces and stress
to consider completed the task. If this does not happen in a single Siesta run, the workchain restarts
automatically the relaxation. The maximum number of restarts is specified with the keyword **max_iterations**,
as explained in the previous subsection.


Submitting the WorkChain
------------------------

WorkChains are submitted in AiiDA exacly like any other calculation. Therefore::

        from aiida_siesta.workflows.base import SiestaBaseWorkChain
        from aiida.engine import
        builder = SiestaBaseWorkChain.get_builder()
        builder.options = options
        ... All the inputs here ...
        submit(builder) #or run

There is no need to set the computational resources with the metadata as they are already
defined in the input **options**, however ``builder.metadata.label`` and ``builder.metadata.description``
could be used to label and describe the WorkChain.
Again, the use of the ``builder`` is not mandatory, the inputs can be passed as arguments of
``sumbit``/``run`` as explained in the siesta plugin section.

Outputs
-------

The outputs of the **SiestaBaseWorkChain** mirror exactly the one of the siesta plugin.
Therefore all the information can be obtained in the :ref:`corresponding section <outputs-siesta-calc>`.


.. _basewc-error:

Error handling
--------------

We list here the errors that are handled by the **SiestaBaseWorkChain** and the
corresponding action taken. The error are actually detected by the siesta parser,
in the WorkChain, the handling is performed.

* **SCF_NOT_CONV**

  When the convergence of the self-consistent cycle is not reached in ``max-scf-iterations`` or
  in the allocated ``max_walltime``, siesta raises the **SCF_NOT_CONV** error.
  The **SiestaBaseWorkChain** is able to detect this error and restart the calculation with no
  modifications on the input parameters.

.. |br| raw:: html

    <br />

* **GEOM_NOT_CONV**

  When the convergence of the geometry (during a relaxation) is not reached
  in the allocated ``max_walltime``, siesta raises the **GEOM_NOT_CONV** error.
  The **SiestaBaseWorkChain** is able to detect this error and restart the calculation with no
  modifications on the input parameters.

.. |br| raw:: html

    <br />

* **SPLIT_NORM**

  The **SiestaBaseWorkChain** deals with problems connected to the basis set creation.
  If a "too small split-norm" error is detected, the WorkChains reacts in two ways.
  If a global split-norm was defined in input through ``pao-split-norm``, its value is reset to
  the minimum acceptable. If no global split-norm was defined the option ``pao-split-tail-norm = True``
  is set.

Two more errors are detected by the WorkChain, but not handled at the moment,
only a specific error code is returned as output without attempting a restart.

* **BASIS_POLARIZ**

  If an error on the polarization of one orbital is detected, the error code 403 is returned.
  The solution to this problem is to set the "non-perturbative" polarization scheme for the
  element that presents an error, however this possibility is available only in recent
  versions of AiiDA, making inconvenient to treat automatically the resolution of this error.

.. |br| raw:: html

    <br />

* **ERROR_BANDS**

  If a calculation of the electronic bands is requested, but
  an error in the parsing of the bands file is detected, the error code 404 is returned.
  In this case, the WorkChain will anyway return all the other outputs because the checks
  on the bands file are always performed at the very end of the calculation.

The **SiestaBaseWorkChain** also inherits the error codes of the **BaseRestartWorkChain**
of the aiida-core distribution. For instance,
if an unexpected error is raised twice, the workchain finishes with exit code 402, if the
maximum number of iterations is reached, error 401 is returned. More in the section
`BaseRestartWorkChain`_ of the aiida-core package.

Protocol system
---------------

The protocol system is available for this WorkChain. The ``SiestaBaseWorkChain.inputs_generator()``
makes available all the methods explained in the :ref:`protocols documentation <how-to>`. For example::

        from aiida_siesta.workflows.base import SiestaBaseWorkChain
        inp_gen = SiestaBaseWorkChain.inputs_generator()
        builder = inp_gen.get_filled_builder(structure, calc_engines, protocol)
        #here user can modify builder befor submission.
        submit(builder)

is sufficient to submit a **SiestaBaseWorkChain** on ``structure`` following the specifications of
``protocols`` and computational resources collected in ``calc_engines``.
The structure of ``calc_engines`` is the same as for the **SiestaCalculation** input generator
(again see :ref:`protocols documentation <how-to>`).


.. _BaseRestartWorkChain: https://aiida.readthedocs.io/projects/aiida-core/en/latest/reference/apidoc/aiida.engine.processes.html?highlight=baserestart#aiida.engine.processes.BaseRestartWorkChain
