import unicodedata
import random
import logging
import argostranslate.translate

def translate_en_fa(article_en):
    result = argostranslate.translate.translate(article_en, 'en', 'fa',)
    return result


def translate_fa_en(article_fa):
    result = argostranslate.translate.translate(article_fa, 'fa', 'en',)
    return result


def translate_ar_en(article_ar):
    result = argostranslate.translate.translate(article_ar, 'ar', 'en',)
    return result


def translate_en_ar(article_en):
    article_en = article_en.replace('(', '')
    article_en = article_en.replace(')', '')
    result = argostranslate.translate.translate(article_en, 'en', 'ar',)
    result =result.replace('&quot;', '"')
    return result


def translate_fa_ar(article_fa):
    article_en = translate_fa_en(article_fa)
    result = translate_en_ar(article_en)
    return result


def translate_ar_fa(article_ar):
    article_en = translate_ar_en(article_ar)
    result = translate_en_fa(article_en)
    return result


def translate(article, source_lang, target_lang):
    if source_lang == 'en' and target_lang == 'fa':
        return translate_en_fa(article)
    elif source_lang == 'fa' and target_lang == 'en':
        return translate_fa_en(article)
    elif source_lang == 'ar' and target_lang == 'en':
        return translate_ar_en(article)
    elif source_lang == 'en' and target_lang == 'ar':
        return translate_en_ar(article)
    elif source_lang == 'fa' and target_lang == 'ar':
        return translate_fa_ar(article)
    elif source_lang == 'ar' and target_lang == 'fa':
        return translate_ar_fa(article)
    else:
        return "Invalid input"
    

def generate_random_numbers(n, k):
    return random.sample(range(k+1), n)


def detect_language(text):
    text_length = len(text)
    if text_length < 500:
        n_test_chars = text_length
    elif text_length < 2000:
        n_test_chars = 0.8 * text_length
    elif text_length < 4000:
        n_test_chars = 0.75 * text_length
    elif text_length < 6000:
        n_test_chars = 0.7 * text_length
    elif text_length < 8000:
        n_test_chars = 0.65 * text_length
    elif text_length < 10000:
        n_test_chars = 0.6 * text_length
    elif text_length < 20000:
        n_test_chars = 0.5 * text_length
    else:
        n_test_chars = 10000

    n_test_chars = int(n_test_chars)

    test_indices = random.sample(range(text_length), n_test_chars)
    test_chars = [text[i] for i in test_indices]

    persian_counter, english_counter = 1, 1
    for char in test_chars:
        try:
            if 'ARABIC' in unicodedata.name(char) or 'PERSIAN' in unicodedata.name(char):
                persian_counter += 1
            elif 'LATIN' in unicodedata.name(char):
                if not char.isdigit(): 
                    english_counter += 1
        except:
            continue
        
    per_to_eng_ratio = persian_counter / english_counter
    if per_to_eng_ratio >= 2:
        return "Persian"
    elif per_to_eng_ratio <= 0.33:
        return "English"
    else:
        return None



    