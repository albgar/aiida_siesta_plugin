import pytest
from aiida.common.exceptions import StoringNotAllowed

def test_ions(generate_ion_data):

    ion = generate_ion_data('Si')

    assert ion.element == "Si"
    assert ion.name == "Si"
    assert ion.atomic_number == 14
    assert ion.mass == 28.09
    assert ion.is_stored == False
    ion.store()
    assert ion.is_stored == True


def test_ions_validators(generate_ion_data):

    ion = generate_ion_data('Si')

    ion.attributes["element"] = "new_name"
    assert ion.is_stored == False
    assert ion.element == "new_name"
    with pytest.raises(StoringNotAllowed):
        ion.store()

    ion = generate_ion_data('Si')

    ion.attributes["md5"] = "weee"
    assert ion.is_stored == False
    assert ion.md5 == "weee"
    with pytest.raises(StoringNotAllowed):
        ion.store()

    ion = generate_ion_data('Si')

    ion.attributes["atomic_number"] = 22
    assert ion.is_stored == False
    assert ion.atomic_number == 22
    with pytest.raises(StoringNotAllowed):
        ion.store()

    ion = generate_ion_data('Si')

    ion.attributes["name"] = "namee"
    assert ion.is_stored == False
    assert ion.name == "namee"
    with pytest.raises(StoringNotAllowed):
        ion.store()


def test_get_or_create(generate_ion_data):

    from aiida_siesta.data.ion import IonData
    import os
    filename = os.path.join('tests', 'fixtures', 'ions', 'SiDiff.ion.xml')
    filepath = os.path.abspath(filename)

    ion, created = IonData.get_or_create(filepath)
    assert created == True
    assert ion.is_stored == False
    ion.store()
    assert ion.is_stored == True

    #Now it is stored! Therefore a new call will say that is not created
    ion, created = IonData.get_or_create(filepath)
    assert created == False
    assert ion.is_stored == True

    #Now we created a second ion with same md5. Raise error unless `use_first`
    new = IonData(filepath)
    new.store()
    with pytest.raises(ValueError):
        ion, created = IonData.get_or_create(filepath)
    ion, created = IonData.get_or_create(filepath, use_first = True)

    #Finally test store_ion True
    filename = os.path.join('tests', 'fixtures', 'ions', 'SiTris.ion.xml')
    filepath = os.path.abspath(filename)
    ion, created = IonData.get_or_create(filepath, store_ion=True)
    assert ion.is_stored == True

def test_get_orbitals(generate_ion_data):

    from aiida_siesta.data.atomic_orbitals import SislAtomicOrbital
    ion = generate_ion_data('Si')
    orbit_list = ion.get_orbitals()
    assert len(orbit_list) == 18
    assert isinstance(orbit_list[0],SislAtomicOrbital)
