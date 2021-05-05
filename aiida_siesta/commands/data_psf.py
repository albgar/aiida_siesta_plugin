"""Implements the `verdi data psf` command."""

import io
import os
import click

from aiida.cmdline.commands.cmd_data import verdi_data
from aiida.cmdline.params import arguments, options
from aiida.cmdline.utils import decorators, echo


@verdi_data.group('psf')
def psf():
    """Manipulate PsfData objects (PSF-format pseudopotentials)."""


@psf.command('uploadfamily')
@click.argument('folder', type=click.Path(exists=True, file_okay=False, resolve_path=True))
@click.argument('group_label', type=click.STRING)
@click.argument('group_description', type=click.STRING)
@click.option(
    '--stop-if-existing',
    is_flag=True,
    default=False,
    help='Interrupt pseudos import if a pseudo was already present in the AiiDA database'
)
@decorators.with_dbenv()
@decorators.deprecated_command(
    "This command has been deprecated and will be removed in v2.0. Please use `aiida-pseudo install` instead."
)
def psf_uploadfamily(folder, group_label, group_description, stop_if_existing):
    """
    Create a new PSF family from a folder of PSF files.

    Returns the numbers of files found and the number of nodes uploaded.

    Call without parameters to get some help.
    """
    from aiida_siesta.data.psf import upload_psf_family
    files_found, files_uploaded = upload_psf_family(folder, group_label, group_description, stop_if_existing)
    echo.echo_success('PSF files found: {}. New files uploaded: {}'.format(files_found, files_uploaded))


@psf.command('listfamilies')
@click.option(
    '-d',
    '--with-description',
    'with_description',
    is_flag=True,
    default=False,
    help='Show also the description for the PSF family'
)
@options.WITH_ELEMENTS()
@decorators.with_dbenv()
@decorators.deprecated_command(
    "This command is deprecated and will be removed in aiida_siesta v2.0. Its substitute command is `aiida-pseudo "
    "list`. Since the pseudo management is now based on a new system, the families listed here will not appear "
    "running the new command. It is suggested to export the families into a folder (`verdi data psf exportfamily "
    "folder_name family_label`), delete the group corresponding to the family (`verdi group delete family_label`), "
    "and install the family again (`aiida-pseudo install family folder_name family_label -P pseudo.psf`)."
)
def psf_listfamilies(elements, with_description):
    """
    List all PSF families that exist in the database.
    """
    from aiida import orm
    from aiida.plugins import DataFactory
    from aiida_siesta.groups.pseudos import PsfFamily

    PsfData = DataFactory('siesta.psf')  # pylint: disable=invalid-name
    query = orm.QueryBuilder()
    query.append(PsfData, tag='psfdata')
    if elements is not None:
        query.add_filter(PsfData, {'attributes.element': {'in': elements}})
    query.append(PsfFamily, with_node='psfdata', tag='group', project=['label', 'description'])

    query.distinct()
    if query.count() > 0:
        for res in query.dict():
            group_label = res.get('group').get('label')
            group_desc = res.get('group').get('description')
            query = orm.QueryBuilder()
            query.append(orm.Group, tag='thisgroup', filters={'label': {'like': group_label}})
            query.append(PsfData, project=['id'], with_group='thisgroup')

            if with_description:
                description_string = ': {}'.format(group_desc)
            else:
                description_string = ''

            echo.echo_success('* {} [{} pseudos]{}'.format(group_label, query.count(), description_string))

    else:
        echo.echo_warning('No valid PSF pseudopotential family found.')


@psf.command('exportfamily')
@click.argument('folder', type=click.Path(exists=True, file_okay=False, resolve_path=True))
@arguments.GROUP()
@decorators.deprecated_command("This command has been deprecated and will be removed in v2.0.")
@decorators.with_dbenv()
def psf_exportfamily(folder, group):
    """
    Export a pseudopotential family into a folder.
    Call without parameters to get some help.
    """
    if group.is_empty:
        echo.echo_critical('Group<{}> contains no pseudos'.format(group.label))

    for node in group.nodes:
        dest_path = os.path.join(folder, node.filename)
        if not os.path.isfile(dest_path):
            with io.open(dest_path, 'w', encoding='utf8') as handle:
                handle.write(node.get_content())
        else:
            echo.echo_warning('File {} is already present in the destination folder'.format(node.filename))


@psf.command('import')
@click.argument('filename', type=click.Path(exists=True, dir_okay=False, resolve_path=True))
@decorators.deprecated_command("This command has been deprecated and will be removed in v2.0.")
@decorators.with_dbenv()
def psf_import(filename):
    """
    Import a PSF pseudopotential from a file.
    """
    from aiida_siesta.data.psf import PsfData

    node, _ = PsfData.get_or_create(filename)
    echo.echo_success('Imported: {}'.format(node))
