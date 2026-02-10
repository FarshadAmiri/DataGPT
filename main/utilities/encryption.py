# from Cryptodome.PublicKey import RSA
from Cryptodome.Cipher import PKCS1_v1_5
from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Random import get_random_bytes
import base64
from Cryptodome.PublicKey import RSA
from Cryptodome.Cipher import PKCS1_v1_5
from base64 import b64decode


def decode_chuncks(encrypted_chunks, lang, chunkded=False):
    with open('private_key.pem', 'rb') as f:
        private_key_data = f.read()
    private_key = RSA.import_key(private_key_data)
    # print(f"\private_key: {private_key}\n")
    cipher = PKCS1_v1_5.new(private_key)

    if chunkded == False:
        encrypted_chuncks = [encrypted_chunks]

    decrypted_chuncks = []
    for txt in encrypted_chuncks:
        txt_bytes = b64decode(txt)
        decrypted_bytes = cipher.decrypt(txt_bytes, None)
        decrypted_text = decrypted_bytes.decode('utf-8')
        if lang == "Persian":
            decrypted_text = b64decode(decrypted_text).decode('utf-8')
        decrypted_chuncks.append(decrypted_text)

    decrypted_text = "".join(decrypted_chuncks)
    return decrypted_text

def encrypt3(raw, encrypted_aes_key):
        aes_key = decode_RSA(encrypted_aes_key).encode('utf-8')
        aes_key = base64.b64decode(aes_key)
        raw = pad(raw.encode(),16)
        cipher = AES.new(aes_key.encode('utf-8'), AES.MODE_ECB)
        return base64.b64encode(cipher.encrypt(raw))


def encrypt_and_chunck(text, lang):
    with open('public_key.pem', 'rb') as f:
        public_key_data = f.read()
    public_key = RSA.import_key(public_key_data)
    # print(f"\public_key: {public_key}\n")
    cipher = PKCS1_v1_5.new(public_key)

    if lang == "Persian":
        text = text.encode('utf-8')

    encrypted_chunks = []
    for i in range(0, len(text), 128):
        chunk = text[i:i + 128]
        encrypted_bytes = cipher.encrypt(chunk)
        encrypted_chunk = base64.b64encode(encrypted_bytes).decode('utf-8')
        encrypted_chunks.append(encrypted_chunk)
        

def decode_RSA(encrypted_text, private_key_path:str='private_key.pem'):
    if encrypted_text is None or encrypted_text == '':
        raise ValueError("encrypted_text cannot be None or empty")
    with open(private_key_path, 'rb') as f:
        private_key_data = f.read()
    private_key = RSA.import_key(private_key_data)
    cipher = PKCS1_v1_5.new(private_key)
    decrypted_bytes = base64.b64decode(encrypted_text)
    decrypted_text = cipher.decrypt(decrypted_bytes, None).decode('utf-8')
    return decrypted_text


def decrypt_AES_CBC(encrypted_text, encrypted_aes_key):
    aes_key = decode_RSA(encrypted_aes_key).encode('utf-8')
    aes_key = base64.b64decode(aes_key)
    # print(f"\naes_key: {aes_key}\n")
    iv = aes_key  # Use the AES key as the initialization vector (IV)
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    decrypted_text = cipher.decrypt(base64.b64decode(encrypted_text)).decode('utf-8').strip()
    return decrypted_text, aes_key

def decrypt_aes_key(encrypted_aes_key):
    if encrypted_aes_key is None or encrypted_aes_key == '':
        raise ValueError("encrypted_aes_key cannot be None or empty")
    # decrypting AES key with our RSA private key
    aes_key = decode_RSA(encrypted_aes_key).encode('utf-8')
    aes_key = base64.b64decode(aes_key)
    # print(f"\naes_key: {aes_key}\n")
    return aes_key

def decrypt_AES_ECB(encrypted_text, aes_key):
    cipher = AES.new(aes_key, AES.MODE_ECB)
    decrypted_text = cipher.decrypt(base64.b64decode(encrypted_text)).decode('utf-8').strip()
    return decrypted_text


from Crypto.Util.Padding import pad, unpad
# def encrypt_AES(text, aes_key):
#     iv = get_random_bytes(16)  # Use the AES key as the initialization vector (IV) for demonstration purposes
#     cipher = AES.new(aes_key, AES.MODE_CBC, iv)
#     padded_text = pad(text.encode('utf-8'), 16)
#     encrypted_text = cipher.encrypt(padded_text)
#     encrypted_text = base64.b64encode(encrypted_text)
#     return decrypt_AES(encrypted_text, aes_key)[0]

from Crypto import Random
def encrypt_AES(plain_text, aes_key):
    # Assuming aes_key is already in bytes form and properly decoded from base64 if it was encoded
    if isinstance(aes_key, str):
        aes_key = base64.b64decode(aes_key.encode('utf-8'))
    
    # Generate a random IV, do not reuse the AES key as the IV
    iv = Random.new().read(AES.block_size)
    
    # Create cipher object and encrypt the data
    cipher = AES.new(aes_key, AES.MODE_CBC, iv)
    padded_data = pad(plain_text.encode('utf-8'), AES.block_size)
    encrypted_text = cipher.encrypt(padded_data)
    encrypted_text = base64.b64encode(iv + encrypted_text)
    
    # Returning the encrypted data and the IV so that decryption can occur
    return encrypted_text, iv # Prepend the IV to the encrypted data for use in decryption


def encrypt_AES_ECB(plain_text, aes_key):
    # Assuming aes_key is already in bytes form and properly decoded from base64 if it was encoded
    if isinstance(aes_key, str):
        aes_key = base64.b64decode(aes_key.encode('utf-8'))
    
    # Create cipher object and encrypt the data
    cipher = AES.new(aes_key, AES.MODE_ECB)
    padded_data = pad(plain_text.encode('utf-8'), AES.block_size)
    encrypted_text = cipher.encrypt(padded_data)
    encrypted_text = base64.b64encode(encrypted_text)
    
    # Returning the encrypted data and the IV so that decryption can occur
    return encrypted_text # Prepend the IV to the encrypted data for use in decryption