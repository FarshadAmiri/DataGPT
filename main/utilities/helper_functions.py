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