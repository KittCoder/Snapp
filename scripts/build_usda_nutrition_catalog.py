"""Build a compact, offline ingredient nutrition catalog from official USDA files."""
import gzip
import hashlib
import json
from pathlib import Path
from urllib.request import urlretrieve
import zipfile

ROOT = Path(__file__).resolve().parents[1]
SOURCES = {
 'sr_legacy': 'https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_sr_legacy_food_json_2018-04.zip',
 'foundation': 'https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_foundation_food_json_2026-04-30.zip',
}
NUTRIENTS = {1003:'protein_g',1004:'fat_g',1005:'carbohydrates_g',1008:'calories',1079:'fiber_g',2000:'sugars_g',1093:'sodium_mg',2047:'calories',2048:'calories'}

def build():
 directory=ROOT/'data/usda_nutrition';directory.mkdir(parents=True,exist_ok=True)
 foods=[];sources=[]
 for name,url in SOURCES.items():
  archive=directory/f'{name}.zip'
  if not archive.exists():urlretrieve(url,archive)
  sources.append({'url':url,'sha256':hashlib.sha256(archive.read_bytes()).hexdigest()})
  with zipfile.ZipFile(archive) as zipped:
   data=json.loads(zipped.read(next(path for path in zipped.namelist() if path.endswith('.json'))))
  for food in next(value for value in data.values() if isinstance(value,list)):
   if not isinstance(food,dict):continue
   nutrients={}
   for row in food.get('foodNutrients') or []:
    if not isinstance(row,dict):continue
    key=NUTRIENTS.get((row.get('nutrient') or {}).get('id'));value=row.get('amount')
    if key and isinstance(value,(int,float)):nutrients.setdefault(key,value)
   if not all(key in nutrients for key in ('protein_g','fat_g','carbohydrates_g')):continue
   portions=[{'amount':p.get('amount') or p.get('value') or 1,'grams':p['gramWeight'],
              'unit':p.get('measureUnit',{}).get('name',''),
              'description':p.get('modifier') or p.get('portionDescription') or ''}
             for p in food.get('foodPortions') or [] if isinstance(p,dict) and p.get('gramWeight')]
   foods.append({'fdc_id':food['fdcId'],'description':food['description'],'data_type':food['dataType'],
                 'nutrients_per_100g':nutrients,'portions':portions})
 catalog={'source':'USDA FoodData Central','sources':sources,'foods':foods}
 output=ROOT/'Model/usda_nutrition_catalog.json.gz'
 with output.open('wb') as stream,gzip.GzipFile(fileobj=stream,mode='wb',mtime=0) as compressed:
  compressed.write(json.dumps(catalog,separators=(',',':')).encode())
 print(f'{len(foods)} USDA foods; catalog {output.stat().st_size:,} bytes')

if __name__=='__main__':build()
