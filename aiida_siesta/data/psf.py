"""
This module manages the PSF pseudopotentials in the local repository.
"""
#pylint: disable=redefined-outer-name,too-many-statements

import warnings
import io
from aiida.common.files import md5_file
from aiida.orm.nodes import SinglefileData
from aiida_siesta.utils.warn import AiidaSiestaDeprecationWarning


def get_pseudos_from_structure(structure, family_name):
    """
    Given a family name (a PsfFamily group in the DB) and a AiiDA
    structure, return a dictionary associating each kind name with its
    PsfData object.

    :raise MultipleObjectsError: if more than one PSF for the same element is
       found in the group.
    :raise NotExistent: if no PSF for an element in the group is
       found in the group.
    """
    from aiida.common.exceptions import NotExistent, MultipleObjectsError

    message = (  #pylint: disable=invalid-name
        'This function has been deprecated and will be removed in `v2.0.0`. ' +
        '`get_pseudos_from_structure` is substitued by `fam.get_pseudos(structure=structure)` ' +
        'where `fam` is an instance of the families classes in `aiida_pseudo.groups.family`.'
    )

    warnings.warn(message, AiidaSiestaDeprecationWarning)

    family_pseudos = {}
    family = PsfData.get_psf_group(family_name)
    for node in family.nodes:
        if isinstance(node, PsfData):
            if node.element in family_pseudos:
                raise MultipleObjectsError(
                    "More than one PSF for element {} found in "
                    "family {}".format(node.element, family_name)
                )
            family_pseudos[node.element] = node

    pseudo_list = {}
    for kind in structure.kinds:
        symbol = kind.symbol
        try:
            pseudo_list[kind.name] = family_pseudos[symbol]
        except KeyError:
            raise NotExistent("No PSF for element {} found in family {}".format(symbol, family_name))

    return pseudo_list


def upload_psf_family(folder, group_label, group_description, stop_if_existing=True):
    """
    Upload a set of PSF files in a given group.

    :param folder: a path containing all PSF files to be added.
        Only files ending in .PSF (case-insensitive) are considered.
    :param group_label: the name of the group to create. If it exists and is
        non-empty, a UniquenessError is raised.
    :param group_description: a string to be set as the group description.
        Overwrites previous descriptions, if the group was existing.
    :param stop_if_existing: if True, check for the md5 of the files and,
        if the file already exists in the DB, raises a MultipleObjectsError.
        If False, simply adds the existing PsfData node to the group.
    """
    import os
    from aiida import orm
    from aiida.common import AIIDA_LOGGER as aiidalogger
    from aiida.common.exceptions import UniquenessError
    from aiida.orm.querybuilder import QueryBuilder
    from aiida_siesta.groups.pseudos import PsfFamily

    message = (  #pylint: disable=invalid-name
        'This function has been deprecated and will be removed in `v2.0.0`. ' +
        '`upload_psf_family` is substitued by `fam.create_from_folder` ' +
        'where `fam` is an instance of the families classes in `aiida_pseudo.groups.family`.'
    )

    warnings.warn(message, AiidaSiestaDeprecationWarning)

    if not os.path.isdir(folder):
        raise ValueError("folder must be a directory")

    # only files, and only those ending with .psf or .PSF;
    # go to the real file if it is a symlink
    files = [
        os.path.realpath(os.path.join(folder, i))
        for i in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, i)) and i.lower().endswith('.psf')
    ]

    nfiles = len(files)

    automatic_user = orm.User.objects.get_default()
    group, group_created = PsfFamily.objects.get_or_create(label=group_label, user=automatic_user)

    if group.user.email != automatic_user.email:
        raise UniquenessError(
            "There is already a PsfFamily group with name {}"
            ", but it belongs to user {}, therefore you "
            "cannot modify it".format(group_label, group.user.email)
        )

    # Always update description, even if the group already existed
    group.description = group_description

    # NOTE: GROUP SAVED ONLY AFTER CHECKS OF UNICITY

    pseudo_and_created = []

    for afile in files:
        md5sum = md5_file(afile)
        qb = QueryBuilder()
        qb.append(PsfData, filters={'attributes.md5': {'==': md5sum}})
        existing_psf = qb.first()

        #existing_psf = PsfData.query(dbattributes__key="md5",
        #                            dbattributes__tval = md5sum)

        if existing_psf is None:
            # return the psfdata instances, not stored
            pseudo, created = PsfData.get_or_create(afile, use_first=True, store_psf=False)
            # to check whether only one psf per element exists
            # NOTE: actually, created has the meaning of "to_be_created"
            pseudo_and_created.append((pseudo, created))
        else:
            if stop_if_existing:
                raise ValueError(
                    "A PSF with identical MD5 to "
                    " {} cannot be added with stop_if_existing"
                    "".format(afile)
                )
            existing_psf = existing_psf[0]
            pseudo_and_created.append((existing_psf, False))

    # check whether pseudo are unique per element
    elements = [(i[0].element, i[0].md5sum) for i in pseudo_and_created]
    # If group already exists, check also that I am not inserting more than
    # once the same element
    if not group_created:
        for aiida_n in group.nodes:
            # Skip non-pseudos
            if not isinstance(aiida_n, PsfData):
                continue
            elements.append((aiida_n.element, aiida_n.md5sum))

    elements = set(elements)  # Discard elements with the same MD5, that would
    # not be stored twice
    elements_names = [e[0] for e in elements]

    if not len(elements_names) == len(set(elements_names)):
        duplicates = {x for x in elements_names if elements_names.count(x) > 1}
        duplicates_string = ", ".join(i for i in duplicates)
        raise UniquenessError("More than one PSF found for the elements: " + duplicates_string + ".")

    # At this point, save the group, if still unstored
    if group_created:
        group.store()

    # save the psf in the database, and add them to group
    for pseudo, created in pseudo_and_created:
        if created:
            pseudo.store()

            aiidalogger.debug("New node {} created for file {}".format(pseudo.uuid, pseudo.filename))
        else:
            aiidalogger.debug("Reusing node {} for file {}".format(pseudo.uuid, pseudo.filename))

    # Add elements to the group all togetehr
    group.add_nodes([pseudo for pseudo, created in pseudo_and_created])

    nuploaded = len([_ for _, created in pseudo_and_created if created])

    return nfiles, nuploaded


def parse_psf(fname, check_filename=True):
    """
    Try to get relevant information from the PSF. For the moment, only the
    element name.
    If check_filename is True, raise a ParsingError exception if the filename
    does not start with the element name.
    """
    import os

    from aiida.common.exceptions import ParsingError
    # from aiida.common import AIIDA_LOGGER
    from aiida.orm.nodes.data.structure import _valid_symbols

    parsed_data = {}

    try:
        psf_contents = fname.read().split()
        fname = fname.name
    except AttributeError:
        with io.open(fname, encoding='utf8') as fil:
            psf_contents = fil.read().split()

    # Parse the element
    element = None
    for element in psf_contents:
        break

    # Only first letter capitalized!
    if element is None:
        raise ParsingError("Unable to find the element of PSF {}".format(fname))
    element = element.capitalize()
    if element not in _valid_symbols:
        raise ParsingError("Unknown element symbol {} for file {}".format(element, fname))

    if check_filename:
        if not os.path.basename(fname).lower().startswith(element.lower()):
            raise ParsingError(
                "Filename {0} was recognized for element "
                "{1}, but the filename does not start "
                "with {1}".format(fname, element)
            )

    parsed_data['element'] = element

    return parsed_data


class PsfData(SinglefileData):
    """
    Function not yet documented.
    """

    def __init__(self, file, filename=None, **kwargs):
        message = (  #pylint: disable=invalid-name
            'This module has been deprecated and will be removed in `v2.0.0`. Support on psf pseudos and ' +
            'corresponding families is moved to the `aiida_pseudo` package. Use the `PsfData` class of ' +
            'aiida_pseudo.data.pseudo.psf. Instanciating the new class requires a file stream, not the file name.'
        )
        warnings.warn(message, AiidaSiestaDeprecationWarning)

        super().__init__(file, filename, **kwargs)

    @classmethod
    def get_or_create(cls, filename, use_first=False, store_psf=True):
        """
        Pass the same parameter of the init; if a file with the same md5
        is found, that PsfData is returned.

        :param filename: an absolute filename on disk
        :param use_first: if False (default), raise an exception if more than \
                one potential is found.\
                If it is True, instead, use the first available pseudopotential.
        :param bool store_psf: If false, the PsfData objects are not stored in
                the database. default=True.
        :return (psf, created): where psf is the PsfData object, and create is either\
            True if the object was created, or False if the object was retrieved\
            from the DB.
        """
        import os

        message = (  #pylint: disable=invalid-name
            'This method has been deprecated and will be removed in `v2.0.0`. Support on psf pseudos and ' +
            'corresponding families is moved to the aiida_pseudo package. The `get_or_create` method of ' +
            'aiida_pseudo.data.pseudo.psml.Psf requires file stream as argument, not the file name.'
        )
        warnings.warn(message, AiidaSiestaDeprecationWarning)

        if not os.path.abspath(filename):
            raise ValueError("filename must be an absolute path")

        md5 = md5_file(filename)

        pseudos = cls.from_md5(md5)
        if not pseudos:
            instance = cls(file=filename)
            if store_psf:
                instance.store()
            return (instance, True)

        if len(pseudos) > 1:
            if use_first:
                return (pseudos[0], False)

            raise ValueError(
                "More than one copy of a pseudopotential "
                "with the same MD5 has been found in the "
                "DB. pks={}".format(",".join([str(i.pk) for i in pseudos]))
            )

        return (pseudos[0], False)

    def store(self, *args, **kwargs):  # pylint: disable=arguments-differ
        """
        Store the node, reparsing the file so that the md5 and the element
        are correctly reset.
        """
        from aiida.common.exceptions import ParsingError
        from aiida.common.files import md5_from_filelike

        if self.is_stored:
            return self

        with self.open(mode='r') as handle:
            parsed_data = parse_psf(handle)

        # Open in binary mode which is required for generating the md5 checksum
        with self.open(mode='rb') as handle:
            md5sum = md5_from_filelike(handle)

        try:
            element = parsed_data['element']
        except KeyError:
            raise ParsingError("No 'element' parsed in the PSF file {};" " unable to store".format(self.filename))

        self.set_attribute('element', str(element))
        self.set_attribute('md5', md5sum)

        return super(PsfData, self).store(*args, **kwargs)

    @classmethod
    def from_md5(cls, md5):
        """
        Return a list of all PSF pseudopotentials that match a given MD5 hash.

        Note that the hash has to be stored in a _md5 attribute, otherwise
        the pseudo will not be found.
        """
        from aiida.orm.querybuilder import QueryBuilder
        qb = QueryBuilder()
        qb.append(cls, filters={'attributes.md5': {'==': md5}})
        return [_ for [_] in qb.all()]

    def set_file(self, filename):  # pylint: disable=arguments-differ
        """
        I pre-parse the file to store the attributes.
        """
        from aiida.common.exceptions import ParsingError

        parsed_data = parse_psf(filename)
        md5sum = md5_file(filename)

        try:
            element = parsed_data['element']
        except KeyError:
            raise ParsingError("No 'element' parsed in the PSF file {};" " unable to store".format(self.filename))

        super(PsfData, self).set_file(filename)

        # self._set_attr('element', str(element))
        # self._set_attr('md5', md5sum)
        self.set_attribute('element', str(element))
        self.set_attribute('md5', md5sum)

    def get_psf_family_names(self):
        """
        Get the list of all psf family names to which the pseudo belongs
        """
        from aiida.orm import QueryBuilder
        from aiida_siesta.groups.pseudos import PsfFamily

        query = QueryBuilder()
        query.append(PsfFamily, tag='group', project='label')
        query.append(PsfData, filters={'id': {'==': self.id}}, with_group='group')

        return [_[0] for _ in query.all()]

    @property
    def element(self):
        return self.get_attribute('element', None)

    @property
    def md5sum(self):
        return self.get_attribute('md5', None)

    def _validate(self):
        from aiida.common.exceptions import ValidationError
        from aiida.common.files import md5_from_filelike

        super(PsfData, self)._validate()

        with self.open(mode='r') as handle:
            parsed_data = parse_psf(handle)

        # Open in binary mode which is required for generating the md5 checksum
        with self.open(mode='rb') as handle:
            md5 = md5_from_filelike(handle)

        # This is erroneous exception,
        # as it is in the `upf` module oin `aiida_core`
        try:
            element = parsed_data['element']
        except KeyError:
            raise ValidationError("No 'element' could be parsed in the PSF " "file {}".format(self.filename))

        try:
            attr_element = self.get_attribute('element')
        except AttributeError:
            raise ValidationError("attribute 'element' not set.")

        try:
            attr_md5 = self.get_attribute('md5')
        except AttributeError:
            raise ValidationError("attribute 'md5' not set.")

        if attr_element != element:
            raise ValidationError(
                "Attribute 'element' says '{}' but '{}' was "
                "parsed instead.".format(attr_element, element)
            )

        if attr_md5 != md5:
            raise ValidationError("Attribute 'md5' says '{}' but '{}' was " "parsed instead.".format(attr_md5, md5))

    @classmethod
    def get_psf_group(cls, group_label):
        """
        Return the PsfFamily group with the given name.
        """
        from aiida_siesta.groups.pseudos import PsfFamily

        return PsfFamily.get(label=group_label)

    @classmethod
    def get_psf_groups(cls, filter_elements=None, user=None):
        """
        Return all names of groups of type PsfFamily, possibly with some filters.

        :param filter_elements: A string or a list of strings.
               If present, returns only the groups that contains one Psf for
               every element present in the list. Default=None, meaning that
               all families are returned.
        :param user: if None (default), return the groups for all users.
               If defined, it should be either a DbUser instance, or a string
               for the username (that is, the user email).
        """
        from aiida.orm import QueryBuilder
        from aiida.orm import User
        from aiida_siesta.groups.pseudos import PsfFamily

        query = QueryBuilder()
        query.append(PsfFamily, tag='group', project='*')

        if user is not None:
            query.append(User, filters={'email': {'==': user}}, with_group='group')

        if isinstance(filter_elements, str):
            filter_elements = [filter_elements]

        if filter_elements is not None:
            query.append(PsfData, filters={'attributes.element': {'in': filter_elements}}, with_group='group')

        query.order_by({PsfFamily: {'id': 'asc'}})

        return [_[0] for _ in query.all()]
