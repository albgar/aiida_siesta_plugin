from aiida_siesta.utils.protocols_system.generator_absclass import InputGenerator
from aiida.plugins import WorkflowFactory
#from aiida_siesta.groups.pseudos import PsmlFamily
from aiida_pseudo.groups.family.pseudo import PseudoPotentialFamily

def test_validation(aiida_profile):
    """Test the validation of subclasses of `InputsGenerator`."""

    #Here I fake the pseudofamilies
    #PsmlFamily.objects.get_or_create("nc-sr-04_pbe_standard-psf")
    #PsmlFamily.objects.get_or_create("nc-sr-04_pbe_stringent-psf")
    #PsmlFamily.objects.get_or_create("nc-sr-04_pbe_standard_psml")
    PseudoPotentialFamily.objects.get_or_create("PseudoDojo/0.4/PBE/SR/standard/psml")

    class SubInputsGenerator(InputGenerator):

        _calc_types = None

        def get_inputs_dict(self, structure, calc_engines, protocol, **kwargs):

            pass

        def get_filled_builder(self, structure, calc_engines, protocol, **kwargs):

            pass

    import pytest
    with pytest.raises(RuntimeError):
        SubInputsGenerator(WorkflowFactory("siesta.base"))

    class SubInputsGenerator(InputGenerator):

        _calc_types = {"si":{"code": "pp", "resources": "tt"}}

        def get_inputs_dict(self, structure, calc_engines, protocol, **kwargs):

            pass

        def get_filled_builder(self, structure, calc_engines, protocol, **kwargs):

            pass

    import pytest
    with pytest.raises(TypeError):
        SubInputsGenerator()


    class SubInputsGenerator(InputGenerator):

        _calc_types = {"si":{"code": "pp", "resources": "tt"}}

    import pytest
    with pytest.raises(TypeError):
        SubInputsGenerator(WorkflowFactory("siesta.base"))

    class SubInputsGenerator(InputGenerator):

        _calc_types = {"si":{"code": "pp", "resources": "tt"}}

        def get_inputs_dict(self, structure, calc_engines, protocol, **kwargs):

            pass

        def get_filled_builder(self, structure, calc_engines, protocol, **kwargs):

            pass

    subinpgen=SubInputsGenerator(WorkflowFactory("siesta.base")) 
    assert  subinpgen.how_to_pass_computation_options()[1] == {"si":{"code": "pp", "resources": "tt"}}
