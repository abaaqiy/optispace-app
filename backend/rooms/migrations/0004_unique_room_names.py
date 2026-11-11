import re

from django.db import migrations, models


# Freeze the documented aliases used when this identity column was introduced.
ALIASES = {
    '1000seater': '1000seaterlecturetheatre1000slt',
    '1000slt': '1000seaterlecturetheatre1000slt',
    'ageannexi': 'agriculturalengineeringannexlectureroomiagei',
    'ageannexii': 'agriculturalengineeringannexlectureroomiiageii',
    'agei': 'agriculturalengineeringannexlectureroomiagei',
    'ageii': 'agriculturalengineeringannexlectureroomiiageii',
    'aglta': 'agriculturelecturetheatreaaglta',
    'agltb': 'agriculturelecturetheatrebagltb',
    'agltc': 'agriculturelecturetheatrecagltc',
    'ajose': 'ajoselecturetheatreajslt',
    'ajslt': 'ajoselecturetheatreajslt',
    'amphi': 'amphitheatreamphi',
    'architectureaudiovisual': 'architectureaudiovisualstudioformercentralcafeteria',
    'audi': 'auditoriumiaudi',
    'audii': 'auditoriumiiaudii',
    'biologicalsciencebooc': 'booclecturetheatre',
    'bnscdegreedemonstrationroom': 'nursingdemonstrationroom121',
    'bo0a': 'biologicalscienceslecturetheatrebooa',
    'bo0b': 'biologicalscienceslecturetheatreboob',
    'bo0c': 'booclecturetheatre',
    'booa': 'biologicalscienceslecturetheatrebooa',
    'boob': 'biologicalscienceslecturetheatreboob',
    'booc': 'booclecturetheatre',
    'ceg1': 'civilengineeringlecturetheatreicegi',
    'ceg2': 'civilengineeringlecturetheatreiicegii',
    'cegi': 'civilengineeringlecturetheatreicegi',
    'cegii': 'civilengineeringlecturetheatreiicegii',
    'ch102': 'chemistrylecturetheatre102ch102',
    'ch110': 'chemistryseminarroom110ch110',
    'ch202': 'chemistrylecturetheatre202ch202',
    'ch203': 'chemistrylecturetheatre203ch203',
    'ch220': 'chemistryroom220ch220',
    'eslt': 'pharmacylecturetheatreeslt',
    'etf': 'etflecturetheatre',
    'facultyofartsblockiiboardroom402': 'artsblockiiboardroom402',
    'facultyofartsblockiiroom404': 'artsblockiiroom404',
    'facultyofartsblockiroom402': 'artsblockiroom402',
    'facultyofartsblockiroom403': 'artsblockiroom403',
    'facultyofartsblockiroom404': 'artsblockiroom404',
    'facultyoflawroom201': 'lawroom201',
    'facultyoflawroom202': 'lawroom202',
    'facultyoflawroom203': 'lawroom203',
    'facultyoflawroom204': 'lawroom204',
    'facultyoflawroom205': 'lawroom205',
    'facultyoflawroom206': 'lawroom206',
    'facultyoflawroom208': 'lawroom208',
    'facultyoflawroom209': 'lawroom209',
    'fblt': 'firstbanklecturetheatrefblt',
    'healthsciencescommunityhealth': 'communityhealthtutorialroom124',
    'healthsciencesdental': 'dentallecturetheatreextension',
    'healthsciencesmedicalillustrationseminarlab': 'medicalillustrationseminarlaboratory',
    'healthsciencesnursingreadingroom': 'nursingreadingroom130',
    'healthsciencesparttimenursing': 'parttimenursingroom',
    'hsclecturetheatrea': 'healthscienceslecturetheatreahsca',
    'hsclecturetheatreb': 'healthscienceslecturetheatrebhscb',
    'hsclecturetheatrec': 'healthscienceslecturetheatrechscc',
    'hslta': 'healthscienceslecturetheatreahsca',
    'hsltb': 'healthscienceslecturetheatrebhscb',
    'hsltc': 'healthscienceslecturetheatrechscc',
    'law207': 'lawroom207',
    'lgslt': 'localgovernmentstudieslecturetheatre',
    'lgsrdrm': 'localgovernmentstudiesreadingroom',
    'lgsseminarroom2': 'localgovernmentstudiesseminarroomii',
    'lgsseminarroom3': 'localgovernmentstudiesseminarroomiii',
    'lgsseminarroom4': 'localgovernmentstudiesseminarroomiv',
    'lgssrm2': 'localgovernmentstudiesseminarroomii',
    'lgssrm3': 'localgovernmentstudiesseminarroomiii',
    'lgssrm4': 'localgovernmentstudiesseminarroomiv',
    'llti': 'lawlecturetheatreimootandmockcourt',
    'lltii': 'lawlecturetheatreii',
    'mathematicsmbb020': 'yellowhousephasebroommbb020',
    'mathematicsmbb021': 'yellowhousephasebroommbb021',
    'mathematicsmbb022': 'yellowhousephasebroommbb022',
    'mathematicsmbb114': 'yellowhousephasebroommbb114',
    'mathematicsmbb115': 'yellowhousephasebroommbb115',
    'mathematicsmbb116': 'yellowhousephasebroommbb116',
    'mathematicsmbb212': 'yellowhousephasecseminarroommbb212',
    'mathematicsmbb218': 'yellowhousephasebroommbb218',
    'mathematicsmbb219': 'yellowhousephasebroommbb219',
    'mba213': 'mathematicsseminarroommba213',
    'mbb216': 'mathematicslibrarymbb216yellowhousephaseb',
    'mootandmockcourt': 'lawlecturetheatreimootandmockcourt',
    'mqlt': 'pharmacylecturetheatremqlt',
    'odlt1': 'oduduwalecturetheatreiodlti',
    'odlt2': 'oduduwalecturetheatreiiodltii',
    'odlti': 'oduduwalecturetheatreiodlti',
    'odltii': 'oduduwalecturetheatreiiodltii',
    'pgltc': 'postgraduatelecturetheatrecpgltc',
    'pharmacyeslt': 'pharmacylecturetheatreeslt',
    'pharmacymqlt': 'pharmacylecturetheatremqlt',
    'pharmacypharmaceuticslab': 'pharmaceuticslaboratoryroom103',
    'pharmacypharmacognosylab': 'pharmacognosylaboratoryroom210',
    'pharmacypharmacologylab': 'pharmacologylaboratoryroom205206',
    'pharmacypharmchemlab': 'pharmaceuticalchemistrylaboratoryroom106',
    'pharmacypharmchemmainlab': 'pharmaceuticalchemistrymainlaboratoryroom111',
    'py102103': 'physicslecturetheatre102103',
    'py130': 'physicsroom130',
    'py202203': 'physicslecturetheatre202203',
    'sslta': 'socialscienceslecturetheatreasslta',
    'ssltb': 'socialscienceslecturetheatrebssltb',
    'tch1': 'chemicalengineeringandfoodtechnologyroomitchi',
    'tch2': 'chemicalengineeringandfoodtechnologyroomiitchii',
    'tch3': 'chemicalengineeringandfoodtechnologyroomiiitchiii',
    'tchi': 'chemicalengineeringandfoodtechnologyroomitchi',
    'tchii': 'chemicalengineeringandfoodtechnologyroomiitchii',
    'tchiii': 'chemicalengineeringandfoodtechnologyroomiiitchiii',
}


def fill_room_name_keys(apps, schema_editor):
    Room = apps.get_model('rooms', 'Room')
    query = Room.objects.using(schema_editor.connection.alias)
    changes, used, duplicates = [], {}, []
    for room in query.order_by('pk').only('pk', 'code', 'name'):
        name_key = re.sub(r'[^a-z0-9]', '', room.name.casefold())
        name_key = ALIASES.get(name_key, name_key)
        if not name_key:
            raise RuntimeError(f'Room {room.code} needs a name with letters or numbers before rooms.0004.')
        if name_key in used:
            duplicates.append(f'{used[name_key]} / {room.code}')
        used[name_key] = room.code
        changes.append((room.pk, name_key))
    if duplicates:
        raise RuntimeError('Resolve duplicate room names before rooms.0004: ' + ', '.join(duplicates))
    for pk, name_key in changes:
        query.filter(pk=pk).update(name_key=name_key)


class Migration(migrations.Migration):
    dependencies = [('rooms', '0003_require_building_remove_room_zone')]

    operations = [
        migrations.AddField(model_name='room', name='name_key',
                            field=models.CharField(max_length=400, null=True, editable=False)),
        migrations.RunPython(fill_room_name_keys, migrations.RunPython.noop),
        migrations.AlterField(model_name='room', name='name_key',
                              field=models.CharField(max_length=400, unique=True, editable=False)),
        migrations.AddConstraint(model_name='room', constraint=models.CheckConstraint(
            condition=~models.Q(name_key=''), name='room_name_key_required',
        )),
        migrations.AddConstraint(model_name='room', constraint=models.UniqueConstraint(
            models.Func(models.functions.Lower('name'), models.Value('[^a-z0-9]'),
                        models.Value(''), models.Value('g'), function='REGEXP_REPLACE',
                        output_field=models.CharField()),
            name='room_name_normalised_unique',
        )),
    ]
