"""Read-only audit. No migrations, saves, fetches, paid extraction or publishing."""
import collections
import hashlib
import json
import os
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings')
import django
django.setup()
from django.db import connection,transaction
from scrape_me.models import StarterRecipe,Recipe
from scrape_me.api.serializers import RecipeSerializer
from scrape_me.api.starter import serialize

OUT=Path(__file__).resolve().parent
VERBS=r'\b(add|bake|beat|blend|boil|chill|chop|combine|cook|cool|cover|cut|drain|flip|fold|fry|grate|grease|heat|knead|melt|mix|peel|place|pour|preheat|reduce|remove|rinse|roast|roll|saute|sauté|season|serve|simmer|slice|spread|sprinkle|stir|strain|transfer|turn|wash|whisk|wrap)\b'
YIELD = r'\b(?:servings?\s*:\s*\d|serves?\s+(?:(?:around|about)\s+)?\d|yield\s*:\s*\d|makes?\s+(?:(?:about|around)\s+)?\d)'
DURATION=r'\b\d+(?:[.,]\d+)?\s*(?:-\s*\d+\s*)?(?:minutes?|mins?|hours?|hrs?|seconds?|secs?|days?|overnight)\b'

def is_url(value):
    try:
        u=urlsplit(value);return u.scheme in {'https','http'} and bool(u.netloc) and not u.username
    except (ValueError,TypeError):return False

with transaction.atomic():
    with connection.cursor() as cursor:
        cursor.execute('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY')
        cursor.execute('SELECT version()');engine=cursor.fetchone()[0].split(' on ')[0]
    starters=list(StarterRecipe.objects.order_by('id'))
    source=json.loads((ROOT/'data/starter/public-domain-recipes.json').read_text())
    seed={r['slug']:r for r in source['recipes']}
    counts=collections.Counter();bad=[];multi=[];duration=[];groups=[];detail=[];yield_candidates=[]
    keys=collections.Counter();tag_counts=collections.Counter();serial_examples=[]
    totals=collections.Counter()
    for recipe in starters:
        row=recipe.content;p=recipe.provenance;flags=[]
        keys.update(row.keys())
        serializer=RecipeSerializer(data=row)
        if serializer.is_valid():counts['passes_current_save_serializer']+=1
        else:bad.append({'id':recipe.pk,'slug':recipe.slug,'errors':serializer.errors})
        for field in ['ingredients','instructions']:
            values=row.get(field)
            if not isinstance(values,list):flags.append(field+'_not_array');counts[field+'_not_array']+=1;continue
            if not values:counts[field+'_empty']+=1;flags.append(field+'_empty')
            malformed=[i for i,v in enumerate(values) if not isinstance(v,str) or not v.strip()]
            counts[field+'_malformed_items']+=len(malformed)
            if malformed:counts[field+'_with_malformed_items']+=1
            counts[field+'_string_items']+=sum(isinstance(v,str) for v in values)
            counts[field+'_object_items']+=sum(isinstance(v,dict) for v in values)
            if all(isinstance(v,str) for v in values):counts[field+'_all_free_text']+=1
            totals[field]+=len(values)
        y=row.get('yields')
        if y is None or (isinstance(y,str) and not y.strip()):counts['yield_unknown']+=1;flags.append('yield_unknown')
        elif not isinstance(y,str) or len(y)>255:counts['yield_malformed']+=1;flags.append('yield_malformed')
        else:counts['yield_nonempty_text']+=1
        if not y:
            lines=[line for line in recipe.source_markdown.splitlines() if re.search(YIELD,line,re.I)]
            if lines:yield_candidates.append({'id':recipe.pk,'slug':recipe.slug,'lines':lines})
        t=row.get('total_time')
        if t is None:counts['total_time_unknown']+=1;flags.append('total_time_unknown')
        elif type(t) is not int or not 0<=t<=100000:counts['total_time_malformed']+=1;flags.append('total_time_malformed')
        else:counts['total_time_known']+=1
        if re.search(DURATION,row.get('notes',''),re.I):counts['duration_text_in_notes']+=1
        if re.search(DURATION,recipe.source_markdown,re.I):counts['duration_text_in_source']+=1
        if re.search(r'\b(?:prep(?:aration)?|cook(?:ing)?|total|rest(?:ing)?)\s+time\b',row.get('notes',''),re.I):counts['timing_label_in_notes']+=1
        required=['repository','revision','path','source_url','license','license_url','sha256']
        missing=[key for key in required if not isinstance(p.get(key),str) or not p[key].strip()]
        if missing:counts['provenance_incomplete']+=1;flags.append('provenance_incomplete')
        bad_url=[key for key in ['repository','source_url','license_url'] if not is_url(p.get(key))]
        if bad_url:counts['provenance_bad_url']+=1
        if not re.fullmatch(r'[0-9a-f]{40}',p.get('revision','')):counts['provenance_bad_revision']+=1
        if hashlib.sha256(recipe.source_markdown.encode()).hexdigest()!=p.get('sha256'):counts['source_hash_mismatch']+=1
        if not recipe.source_markdown:counts['source_markdown_missing']+=1
        if p.get('source_url')!=row.get('source_url'):counts['source_url_mismatch']+=1
        if not isinstance(p.get('tags'),list) or any(not isinstance(v,str) for v in p.get('tags',[])):counts['tags_malformed']+=1
        else:tag_counts.update(p['tags'])
        if not p.get('tags'):counts['tags_empty']+=1
        if row.get('image'):counts['image_nonempty']+=1
        else:counts['image_unknown']+=1
        if p.get('image_storage'):counts['managed_image_metadata']+=1
        if row.get('title')!=recipe.title:counts['model_content_title_mismatch']+=1
        if recipe.slug in seed:
            changes=[k for k in set(row)|set(seed[recipe.slug]['content']) if row.get(k)!=seed[recipe.slug]['content'].get(k)]
            if changes:counts['differs_from_seed_content']+=1
            if set(changes)-{'image'}:counts['nonimage_difference_from_seed']+=1
        else:counts['not_in_seed']+=1
        headings=re.findall(r'^#{3,4}\s+(.+)',recipe.source_markdown,re.M)
        group_hits=[{'index':i,'text':v} for i,v in enumerate(row.get('ingredients',[])) if any(v.startswith(h.strip()+': ') for h in headings)]
        if group_hits:groups.append({'id':recipe.pk,'slug':recipe.slug,'items':group_hits})
        multisteps=[];durationsteps=[]
        for i,step in enumerate(row.get('instructions',[])):
            verbs=sorted(set(re.findall(VERBS,step.lower())))
            if len(verbs)>=2:multisteps.append({'index':i,'text':step,'action_words':verbs})
            if re.search(DURATION,step,re.I):durationsteps.append(i)
            if len(re.findall(r'[.!?]\s+[A-Z]',step))>=1:counts['multisentence_instruction_items']+=1
        if multisteps:multi.append({'id':recipe.pk,'slug':recipe.slug,'steps':multisteps})
        if durationsteps:duration.append({'id':recipe.pk,'slug':recipe.slug,'step_indexes':durationsteps})
        detail.append({'id':recipe.pk,'slug':recipe.slug,'ingredient_count':len(row.get('ingredients',[])),'instruction_count':len(row.get('instructions',[])), 'gaps':flags})
    sample_candidates=sorted(starters,key=lambda r:len(json.dumps(serialize(r))))
    for recipe in sample_candidates[:3]+[r for r in starters if r.slug in ['apple-pie','lemon-juice-salad-dressing']]:serial_examples.append(serialize(recipe))
    counts['yield_numeric_source_candidates']=len(yield_candidates)
    counts['recipes']=len(starters);counts['seed_recipes']=len(seed)
    counts['multi_action_candidate_recipes']=len(multi)
    counts['multi_action_candidate_steps']=sum(len(r['steps']) for r in multi)
    counts['duration_text_in_step_recipes']=len(duration)
    counts['duration_text_in_step_items']=sum(len(r['step_indexes']) for r in duration)
    counts['group_prefix_recipes']=len(groups)
    counts['group_prefix_ingredient_items']=sum(len(r['items']) for r in groups)
    for key in ['ingredients_empty','instructions_empty','ingredients_not_array','instructions_not_array','ingredients_with_malformed_items','instructions_with_malformed_items','yield_malformed','total_time_malformed','provenance_incomplete','provenance_bad_url','provenance_bad_revision','source_hash_mismatch','source_markdown_missing','source_url_mismatch','model_content_title_mismatch','nonimage_difference_from_seed','not_in_seed']:
        counts.setdefault(key,0)
    private_summary={'rows':Recipe.objects.count(),'owned_rows':Recipe.objects.exclude(owner=None).count(),'ownerless_rows':Recipe.objects.filter(owner=None).count()}
    private=Recipe.objects.exclude(owner=None).order_by('id').first()
    private_shape={key:type(value).__name__ for key,value in RecipeSerializer(private).data.items()} if private else {}
    snapshot= [dict(id=r.pk,slug=r.slug,content=r.content,provenance=r.provenance,source_markdown=r.source_markdown) for r in starters]
    summary={'database_engine':engine,'catalog_sha256':hashlib.sha256(json.dumps(snapshot,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest(),'seed_revision':source['revision'],'counts':dict(sorted(counts.items())),'totals':dict(totals),'content_key_counts':dict(keys),'private_counts':private_summary,'private_serialized_field_types':private_shape,'unique_tags':len(tag_counts),'tags':dict(tag_counts),'current_serializer_failures':bad,'methods':{'multi_action':'At least two distinct exact action words from the fixed regex in audit_catalog.py; a review candidate, not proof of multiple actions or a recipe defect. Negations/quoted words may overcount; synonyms/implicit actions may undercount.','duration':'Explicit numeric-duration regex in notes/source/steps, not a parsed timer.','group_prefix':'Ingredient begins with a source h3/h4 heading plus colon. Conservative: formatted headings may not match.'}}
    for name,data in [('yield-recovery-candidates.json',{'method':YIELD,'count':len(yield_candidates),'candidates':yield_candidates}),('catalog-summary.json',summary),('catalog-row-gaps.json',detail),('multi-action-candidates.json',multi),('group-prefix-examples.json',groups),('current-starter-examples.json',serial_examples)]:
        (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in {'tags','methods'}},ensure_ascii=False,indent=2))
    print('SMALLEST REPRESENTATIVE RECIPES:',[(r.slug,len(r.content['ingredients']),len(r.content['instructions'])) for r in sample_candidates[:8]])
