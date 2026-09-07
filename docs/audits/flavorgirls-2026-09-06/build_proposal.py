"""Build audit-only proposal artifacts. Not imported by either application."""
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent

def obj(properties,required=None):
    return {'type':'object','additionalProperties':False,'required':list(properties) if required is None else required,'properties':properties}
def text(limit=2000):return {'type':'string','minLength':1,'maxLength':limit,'pattern':r'\S'}
def nullable(schema):return {'anyOf':[schema,{'type':'null'}]}
def arr(schema,maximum=200,minimum=0):return {'type':'array','items':schema,'minItems':minimum,'maxItems':maximum}
def ref(name):return {'$ref':'#/$defs/'+name}
def local_id(prefix):return {'type':'string','pattern':f'^{prefix}-[A-Za-z0-9][A-Za-z0-9_-]{{0,63}}$'}
uuid={'type':'string','format':'uuid'}
uri={'type':'string','format':'uri','pattern':'^https?://'}
recipe_id=uuid
sha={'type':'string','pattern':'^[0-9a-f]{64}$'}
D={}
D['Quantity']={'oneOf':[obj({'kind':{'const':'exact'},'value':{'type':'string','pattern':r'^(0|[1-9][0-9]*)(\.[0-9]+)?$'}}),obj({'kind':{'const':'range'},'minimum':{'type':'string','pattern':r'^(0|[1-9][0-9]*)(\.[0-9]+)?$'},'maximum':{'type':'string','pattern':r'^(0|[1-9][0-9]*)(\.[0-9]+)?$'}})]}
D['Unit']=obj({'original_text':text(80),'code':nullable({'enum':['g','kg','mg','mL','L','oz_mass','lb_mass','tsp_us','tbsp_us','cup_us','tsp_metric','tbsp_metric','cup_metric','cup_imperial','count']})})
D['Duration']=obj({'minimum_seconds':{'type':'integer','minimum':0,'maximum':31536000},'maximum_seconds':{'type':'integer','minimum':0,'maximum':31536000},'original_text':nullable(text(500)),'basis':{'enum':['source_explicit','editor_authored']}})
D['Group']=obj({'id':local_id('grp'),'label':text(200)})
D['SourceRef']=obj({'source_id':local_id('src'),'locator':nullable(text(1000))})
D['Ingredient']=obj({'id':local_id('ing'),'original_text':text(2000),'name':nullable(text(200)),'quantity':nullable(ref('Quantity')),'unit':nullable(ref('Unit')),'preparation':nullable(text(1000)),'group_id':nullable(local_id('grp')),'optional':nullable({'type':'boolean'}),'source_refs':arr(ref('SourceRef'),20)})
D['Equipment']=obj({'id':local_id('eq'),'name':text(200),'original_text':nullable(text(1000)),'specification':nullable(text(1000)),'source_refs':arr(ref('SourceRef'),20)})
D['IngredientRef']=obj({'ingredient_id':local_id('ing'),'portion_quantity':nullable(ref('Quantity')),'portion_unit':nullable(ref('Unit')),'original_text':nullable(text(1000))})
D['Timer']=obj({'id':local_id('timer'),'label':text(200),'duration':ref('Duration'),'start_mode':{'const':'user_confirmation'},'completion_condition':nullable(text(1000))})
D['Step']=obj({'id':local_id('step'),'position':{'type':'integer','minimum':1,'maximum':400},'original_text':text(10000),'instruction':text(10000),'group_id':nullable(local_id('grp')),'ingredient_refs':nullable(arr(ref('IngredientRef'))),'unresolved_ingredient_text':nullable(arr(text(200),100)),'equipment_refs':nullable({'type':'array','items':local_id('eq'),'maxItems':100,'uniqueItems':True}),'unresolved_equipment_text':nullable(arr(text(200),100)),'timers':nullable(arr(ref('Timer'),20)),'source_refs':arr(ref('SourceRef'),20)})
D['Source']=obj({'id':local_id('src'),'url':nullable(uri),'author':nullable(text(500)),'repository_url':nullable(uri),'repository_revision':nullable(text(100)),'path':nullable(text(1000)),'source_sha256':nullable(sha),'license':obj({'identifier':nullable(text(100)),'url':nullable(uri),'rights_basis':{'enum':['source_license','user_assertion','unknown']}}),'legacy_locator':nullable(text(1000))})
D['Image']=obj({'id':local_id('img'),'asset_id':{'type':'string','format':'uuid'},'sha256':sha,'alt_text':nullable(text(500)),'origin':{'enum':['source','user_upload','generated_illustration']},'source_url':nullable(uri),'license':nullable(text(200))})
D['Tag']=obj({'vocabulary':{'const':'flavorbuddy-tags/1'},'code':{'enum':['course:breakfast','course:lunch','course:dinner','course:dessert','course:snack','course:drink','method:bake','method:boil','method:fry','method:mix','method:no-cook','dish:salad','dish:soup','dish:bread']}})
properties={'schema_version':{'const':'1.0.0'},'recipe_id':recipe_id,'finalized_at':{'type':'string','format':'date-time'},'title':text(255),'description':nullable(text(10000)),'language':nullable({'type':'string','pattern':'^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$'}),'yield':obj({'original_text':nullable(text(255)),'quantity':nullable(ref('Quantity')),'unit':nullable(text(100))}),'provenance':obj({'origin':{'enum':['imported','manual','ai_generated','derived']},'sources':arr(ref('Source'),20),'inspired_by_recipe_id':nullable(recipe_id),'original_notes':nullable(text(10000))}),'ingredient_groups':nullable(arr(ref('Group'),100)),'ingredients':arr(ref('Ingredient'),200,1),'step_groups':nullable(arr(ref('Group'),100)),'steps':arr(ref('Step'),400,1),'equipment':nullable(arr(ref('Equipment'),100)),'timing':obj({'original_text':nullable(text(2000)),'prep':nullable(ref('Duration')),'cook':nullable(ref('Duration')),'rest':nullable(ref('Duration')),'total':nullable(ref('Duration'))}),'images':nullable(arr(ref('Image'),25)),'tags':nullable({'type':'array','items':ref('Tag'),'maxItems':30,'uniqueItems':True})}
schema={'$schema':'https://json-schema.org/draft/2020-12/schema','$id':'https://flavorbuddy.example/schemas/recipe-document/1.0.0','title':'RecipeDocumentV1 — audit proposal only','description':'Immutable recipe content. Null means unknown/unassessed; empty arrays mean an explicitly assessed absence. Publication, validation results, thumbs feedback and report-driven availability are separate server records. This schema cannot prove culinary correctness, immutable storage or referential integrity.',**obj(properties),'$defs':D}
(OUT/'RecipeDocumentV1.schema.json').write_text(json.dumps(schema,indent=2)+'\n')
# Lossless migration example from the actual Coconut Oil Coffee starter.
# New IDs are illustrative, not database records, and no review/approval is claimed.
current=json.loads((OUT/'current-starter-examples.json').read_text())[0]
p=current['provenance']
example={'schema_version':'1.0.0','recipe_id':'8497679c-a3f6-4d6a-9e50-584c4b34918d','finalized_at':'2026-09-07T02:30:00Z','title':current['title'],'description':None,'language':None,'yield':{'original_text':current['yields'],'quantity':None,'unit':None},'provenance':{'origin':'imported','sources':[{'id':'src-original','url':p['source_url'],'author':current['author'],'repository_url':p['repository'],'repository_revision':p['revision'],'path':p['path'],'source_sha256':p['sha256'],'license':{'identifier':p['license'],'url':p['license_url'],'rights_basis':'source_license'},'legacy_locator':'starter:coconut-oil-coffee'}],'inspired_by_recipe_id':None,'original_notes':None},'ingredient_groups':None,'ingredients':[{'id':f'ing-{name}','original_text':raw,'name':None,'quantity':None,'unit':None,'preparation':None,'group_id':None,'optional':None,'source_refs':[{'source_id':'src-original','locator':f'legacy content.ingredients[{i}]'}]} for i,(name,raw) in enumerate(zip(['coffee','oil','butter'],current['ingredients']))],'step_groups':None,'steps':[{'id':'step-blend','position':1,'original_text':current['instructions'][0],'instruction':current['instructions'][0],'group_id':None,'ingredient_refs':None,'unresolved_ingredient_text':None,'equipment_refs':None,'unresolved_equipment_text':None,'timers':None,'source_refs':[{'source_id':'src-original','locator':'legacy content.instructions[0]'}]}],'equipment':None,'timing':{'original_text':None,'prep':None,'cook':None,'rest':None,'total':None},'images':[],'tags':None}
(OUT/'RecipeDocumentV1.example.json').write_text(json.dumps(example,ensure_ascii=False,indent=2)+'\n')
# A richer schema example with only directly stated fields parsed by this audit.
(OUT/'RecipeDocumentV1.migration-example.json').write_text(json.dumps(example,ensure_ascii=False,indent=2)+'\n')
example['language']='en'
example['yield']['quantity']={'kind':'exact','value':'1'}
example['ingredient_groups']=[];example['step_groups']=[]
for item,name,unit,preparation in zip(example['ingredients'],['coffee','coconut oil','unsalted butter'],['cup','tbsp','tbsp'],['hot',None,None]):
    item['name']=name;item['quantity']={'kind':'exact','value':'1'}
    item['unit']={'original_text':unit,'code':None};item['preparation']=preparation
example['equipment']=[{'id':'eq-blender','name':'blender','original_text':'a blender','specification':None,'source_refs':[{'source_id':'src-original','locator':'legacy content.instructions[0]'}]}]
step=example['steps'][0]
step['ingredient_refs']=[{'ingredient_id':item['id'],'portion_quantity':None,'portion_unit':None,'original_text':name} for item,name in zip(example['ingredients'],['coffee','coconut oil','butter'])]
step['unresolved_ingredient_text']=[];step['equipment_refs']=['eq-blender'];step['unresolved_equipment_text']=[];step['timers']=[]
example['tags']=[{'vocabulary':'flavorbuddy-tags/1','code':'course:drink'},{'vocabulary':'flavorbuddy-tags/1','code':'course:breakfast'}]
# A replacement is a separate immutable recipe, never a revision at the old link.
example['provenance']['inspired_by_recipe_id']=example['recipe_id']
example['recipe_id']='196fdf4d-9ed4-4d02-95f6-9d00ea89094f'
example['finalized_at']='2026-09-07T02:31:00Z'
(OUT/'RecipeDocumentV1.example.json').write_text(json.dumps(example,ensure_ascii=False,indent=2)+'\n')
