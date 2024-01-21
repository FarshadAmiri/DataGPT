import os


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