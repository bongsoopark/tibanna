from __future__ import print_function

import json
import urllib
import boto3 ## 1.4.1 (not the default boto3 on lambda)
import requests 
import time
import sys

sbg_base_url = "https://api.sbgenomics.com/v2"
sbg_project_id = "4dn-dcic/dev"
bucket_for_token = "4dn-dcic-sbg" # an object containing a sbg token is in this bucket 
object_for_token = "token-4dn-labor" # an object containing a sbg token
volume_name = '4dn_s3' # name of the volume to be mounted on sbg.
volume_id = '4dn-labor/' + volume_name # ID of the volume to be mounted on sbg.
object_for_access_key = 's3-access-key-4dn-labor'  # an object containing security credentials for a user 'sbg_s3', who has access to 4dn s3 buckets. It's in the same bucket_for_token. Public_key\nsecret_key. We need this not for the purpose of lambda connecting to our s3, but SBG requires it for mounting our s3 bucket to the sbg s3.


## function that grabs SBG token from a designated S3 bucket
def get_sbg_token (s3):
  try:
    s3.Bucket(bucket_for_token).download_file(object_for_token,'/tmp/'+ object_for_token)  ## lambda doesn't have write access to every place, so use /tmp/.
    with open('/tmp/' + object_for_token,'r') as f:  
      token = f.readline().rstrip()
    return token
  except Exception as e:
    print(e)
    print('Error getting token from S3.')
    raise e


def get_access_key (s3):
  try:
    s3.Bucket(bucket_for_token).download_file(object_for_access_key,'/tmp/'+ object_for_access_key)
    with open('/tmp/' + object_for_access_key,'r') as f:
      access_key = f.read().splitlines()
    return access_key

  except Exception as e:
    print(e)
    print('Error getting access key from S3.')
    raise e


## function that returns a requests response in a nicely indented json format.
def format_response (response):
  return json.dumps(json.loads(response.text), indent=4)


## function that creates volume
def create_volumes (token, volume_name, bucket_name, public_key, secret_key, bucket_object_prefix='', access_mode='rw'):
  volume_url = sbg_base_url + "/storage/volumes/"
  header= { "X-SBG-Auth-Token" : token, "Content-type" : "application/json" }
  data = {
    "name" : volume_name,
    "description" : "some volume" ,
    "service" : {
       "type": "s3",
       "bucket": bucket_name,
       "prefix": bucket_object_prefix, ## prefix of objects, this causs some confusion later when referring to the mounted file, because you have to exclude the prefix part, so just keep it as ''. 
       "credentials": {
         "access_key_id": public_key, ## public access key for our s3 bucket
         "secret_access_key": secret_key  ## secret access key for our s3 bucket
       },
       "properties": {
         "sse_algorithm": "AES256"
       }
    },
    "access_mode" : access_mode  ## either 'rw' or 'ro'.
  }
  response = requests.post(volume_url, headers=header, data=json.dumps(data))
  return(format_response(response))




## function that initiations importing (mounting) an object on 4dn s3 to SBG s3
## token : SBG authentication token
## volume_id : the volume-to-be on SBG s3, e.g. duplexa/myvolume3 (it looks like the first part (duplexa) should match the ownder of the token.)
## source_filename : object key on 4dn s3
## dest_filename : filename-to-be on SBG s3 (default, it is set to be the same as source_filename) 
## return value : the newly imported (mounted) file's ID on SBG S3
def import_volume_content (token, volume_id, object_key, dest_filename=None):

  source_filename = object_key
  if dest_filename is None:
     dest_filename = object_key
  import_url = sbg_base_url + "/storage/imports"
  header= { "X-SBG-Auth-Token" : token, "Content-type" : "application/json" }
  data = {
    "source":{
      "volume": volume_id,
      "location": source_filename
    },
    "destination": {
      "project": sbg_project_id,
      "name": dest_filename
    },
    "overwrite": False
  }
  response = requests.post(import_url, headers=header, data=json.dumps(data))
  return(response.json()['id'])



def get_details_of_import (token, import_id):
  import_url = sbg_base_url + "/storage/imports/" + import_id
  header= { "X-SBG-Auth-Token" : token, "Content-type" : "application/json" }
  data = { "import_id" : import_id }

  ## wait while import is pending
  while True:
    response = requests.get(import_url, headers=header, data=json.dumps(data))
    if response.json()['state'] != 'PENDING':
      break;
    time.sleep(2)

  ## if import failed 
  if response.json()['state'] != 'COMPLETED':
    print(response.json())
    sys.exit() 

  return(response.json())


def create_data_payload_validatefiles ( import_response ):

  try:

     file_id = import_response['result']['id'] # imported Id on SBG
     file_name = import_response['result']['name'] # imported file name on SBG

     app_name = "validate"  

     data = { "app": sbg_project_id + "/" + app_name,
              "project": sbg_project_id,
              "inputs": {
                 "input_file": {
                   "class": "File",
                   "path": file_id,
                   "name": file_name
                 },
                 "type": "fastq"
              } 
            }
     return(data)

  except Exception as e:
     print(e)
     print('Error creating a task payload')
     raise e 


def create_task(token, data):
    url = sbg_base_url + "/tasks"

    headers = {'X-SBG-Auth-Token': token,
               'Content-Type': 'application/json'}

    resp = requests.post(url, headers=headers, data=json.dumps(data))
    print(resp.json())

    if resp.json().has_key('id'):
      return(resp.json()) 
    else:
      print(resp.json())
      sys.exit()


def run_task (token, create_task_response):
    task_id = create_task_response['id']
    url = sbg_base_url + "/tasks/" + task_id + "/actions/run"
    headers = {'X-SBG-Auth-Token': token,
               'Content-Type': 'application/json'}

    data = create_task_response['inputs']
    resp = requests.post(url, headers=headers, data=json.dumps(data))
    return(resp.json()) ## return the run_task response




def lambda_handler(event, context):
    #print("Received event: " + json.dumps(event, indent=2))

    # Get the object from the event and show its content type
    #bucket = event['Records'][0]['s3']['bucket']['name']
    #key = urllib.unquote_plus(event['Records'][0]['s3']['object']['key'].encode('utf8'))
    bucket = event['bucket_name'].encode('utf8')
    key = event['object_key'].encode('utf8')

    ## check the bucket and key
    try:
        s3 = boto3.resource('s3')
        response = s3.Object(bucket, key)

    except Exception as e:
        print(e)
        print('Error getting object {} from bucket {}. Make sure they exist and your bucket is in the same region as this function.'.format(key, bucket))
        raise e
 

    ## get token and access key
    try:
        token = get_sbg_token(s3)
        access_key = get_access_key(s3)

    except Exception as e:
        print(e)
        print('Error getting token and access key from bucket {}.'.format(bucket))
        raise e


    ## mount the bucket and import the file
    try: 
        sbg_create_volume_response = create_volumes (token, volume_name, bucket, public_key=access_key[0], secret_key=access_key[1])
        sbg_import_id = import_volume_content (token, volume_id, key)
        sbg_check_import_response = get_details_of_import(token, sbg_import_id)
        
    except Exception as e:
        print(e)
        print('Error mounting/importing the file to SBG') 
        raise e

    # run a validatefiles task 
    try:
        task_data = create_data_payload_validatefiles ( sbg_check_import_response )
        create_task_response = create_task ( token, task_data )
        run_response = run_task (token, create_task_response)
        return ( run_response )

    except Exception as e:
        print(e)
        print('Error running a task')
        raise e
    


