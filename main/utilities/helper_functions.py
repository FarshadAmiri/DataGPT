import os, shutil
import hashlib


def create_folder(path):
    existed = True
    if not os.path.exists(path):
        os.makedirs(path)
        existed = False
    return existed


def get_first_words(text, character_limitation=60):
    if len(text) <= character_limitation:
        return text
    else:
        space_index = text.rfind(' ', 0, character_limitation)
        if space_index != -1:
            return text[:space_index]
        else:
            return text[:character_limitation]
        

def get_folder_names(directory_path):
    folder_names = []
    for item in os.listdir(directory_path):
        item_path = os.path.join(directory_path, item)
        if os.path.isdir(item_path):
            folder_names.append(item)
    return folder_names


def copy_folder_contents(source, destination, exclude_folder):
    for item in os.listdir(source):
        source_path = os.path.join(source, item)
        destination_path = os.path.join(destination, item)
        if item != exclude_folder:
            if os.path.isdir(source_path):
                shutil.copytree(source_path, destination_path)
            else:
                shutil.copy2(source_path, destination_path)


def hash_file(file_path):
    # BUF_SIZE is totally arbitrary, change for your app!
    BUF_SIZE = 65536  # lets read stuff in 64kb chunks!

    hashes = dict()
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()

    with open(file_path, 'rb') as f:
        while True:
            data = f.read(BUF_SIZE)
            if not data:
                break
            md5.update(data)
            sha256.update(data)
            
    hashes["md5"] = md5.hexdigest()
    hashes["sha256"] = sha256.hexdigest()
    
    return hashes