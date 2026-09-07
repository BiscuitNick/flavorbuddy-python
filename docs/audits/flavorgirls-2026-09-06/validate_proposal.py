"""Audit-only structural/semantic checks. Does not assess recipe quality."""
import copy
from decimal import Decimal
import json
from pathlib import Path
from jsonschema import Draft202012Validator, FormatChecker

ROOT=Path(__file__).resolve().parent
schema=json.loads((ROOT/'RecipeDocumentV1.schema.json').read_text())
Draft202012Validator.check_schema(schema)
validator=Draft202012Validator(schema,format_checker=FormatChecker())

def validate(document):
    validator.validate(document)
    groups={}
    for field in ['ingredients','steps','equipment','ingredient_groups','step_groups']:
        rows=document[field] or []
        ids=[r['id'] for r in rows]
        assert len(ids)==len(set(ids)),f'duplicate {field} ID'
        groups[field]=set(ids)
    assert [s['position'] for s in document['steps']]==list(range(1,len(document['steps'])+1)), 'noncontiguous step order'
    sources={s['id'] for s in document['provenance']['sources']}
    assert len(sources)==len(document['provenance']['sources']),'duplicate source IDs'
    timers=[]
    for item in document['ingredients']:
        assert item['group_id'] is None or item['group_id'] in groups['ingredient_groups']
    for step in document['steps']:
        assert step['group_id'] is None or step['group_id'] in groups['step_groups']
        for link in step['ingredient_refs'] or []:
            assert link['ingredient_id'] in groups['ingredients'],'dangling ingredient reference'
        for equipment in step['equipment_refs'] or []:
            assert equipment in groups['equipment'],'dangling equipment reference'
        for timer in step['timers'] or []:
            timers.append(timer['id'])
            assert timer['duration']['minimum_seconds']>0,'zero timer'
    assert len(timers)==len(set(timers)),'duplicate timer IDs'
    def walk(value):
        if isinstance(value,dict):
            if 'source_refs' in value:
                assert all(r['source_id'] in sources for r in value['source_refs']),'dangling source reference'
            if value.get('kind')=='exact': assert Decimal(value['value'])>0,'nonpositive quantity'
            if value.get('kind')=='range': assert 0<Decimal(value['minimum'])<=Decimal(value['maximum']),'bad quantity range'
            if 'minimum_seconds' in value: assert value['minimum_seconds']<=value['maximum_seconds'],'bad duration range'
            for v in value.values():walk(v)
        elif isinstance(value,list):
            for v in value:walk(v)
    walk(document)

example=json.loads((ROOT/'RecipeDocumentV1.example.json').read_text())
migration=json.loads((ROOT/'RecipeDocumentV1.migration-example.json').read_text())
validate(example);validate(migration)
negative=[]
def rejects(name,mutate):
    doc=copy.deepcopy(example);mutate(doc)
    try:validate(doc)
    except Exception:negative.append(name)
    else:raise AssertionError('Invalid proposal passed: '+name)
rejects('unknown schema version',lambda d:d.update(schema_version='2.0.0'))
rejects('missing title',lambda d:d.pop('title'))
rejects('invalid recipe UUID',lambda d:d.update(recipe_id='not-a-uuid'))
rejects('obsolete revision object',lambda d:d.update(revision={'id':'old'}))
rejects('self-declared feedback totals',lambda d:d.update(thumbs_up=999))
rejects('uncontrolled tag',lambda d:d['tags'].append({'vocabulary':'flavorbuddy-tags/1','code':'allergy:safe'}))
rejects('duplicate ingredient IDs',lambda d:d['ingredients'][1].update(id=d['ingredients'][0]['id']))
rejects('dangling ingredient reference',lambda d:d['steps'][0]['ingredient_refs'][0].update(ingredient_id='ing-missing'))
rejects('dangling equipment reference',lambda d:d['steps'][0].update(equipment_refs=['eq-missing']))
rejects('step position gap',lambda d:d['steps'][0].update(position=2))
rejects('inverted quantity range',lambda d:d['ingredients'][0].update(quantity={'kind':'range','minimum':'2','maximum':'1'}))
rejects('zero ingredient amount',lambda d:d['ingredients'][0].update(quantity={'kind':'exact','value':'0'}))
rejects('automatic timer start',lambda d:d['steps'][0].update(timers=[{'id':'timer-test','label':'Test','duration':{'minimum_seconds':60,'maximum_seconds':60,'original_text':'1 minute','basis':'source_explicit'},'start_mode':'automatic','completion_condition':None}]))
# Exercise optional timer shape without pretending the recipe source stated a duration.
fixture=copy.deepcopy(example)
fixture['steps'][0]['timers']=[{'id':'timer-test','label':'Schema test only','duration':{'minimum_seconds':60,'maximum_seconds':120,'original_text':None,'basis':'editor_authored'},'start_mode':'user_confirmation','completion_condition':None}]
validate(fixture)
summary={'valid_examples':2,'valid_timer_shape_fixture':1,'negative_cases_rejected':negative,'limitations':'No database immutability, publication/availability authorization, culinary correctness, schema migration or withdrawal API implementation is tested by these proposal checks.'}
(ROOT/'proposal-validation.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
