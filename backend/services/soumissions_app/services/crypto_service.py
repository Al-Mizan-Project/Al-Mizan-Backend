import base64
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
# from cryptography.hazmat.primitives import serialization # if we need to export them

class CryptoService:
    @staticmethod
    def generate_key_pair():
        """
        Génère une paire de clés RSA (Publique/Privée) pour un Appel d'Offres.
        (Pour l'instant, on simule l'export au format PEM ou bytes).
        Returns:
            private_key, public_key
        """
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )
        public_key = private_key.public_key()
        return private_key, public_key

    @staticmethod
    def decrypt_aes_key(encrypted_aes_key_base64: str, private_key) -> bytes:
        """
        Déchiffre la clé AES en utilisant la clé privée de l'AO.
        """
        encrypted_aes_key = base64.b64decode(encrypted_aes_key_base64)
        
        # In a real-world scenario, the private_key would be loaded from a PEM/Vault
        # Here we assume `private_key` is a loaded RSA private key object.
        aes_key = private_key.decrypt(
            encrypted_aes_key,
            padding.OAEP(
                mgf=padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None
            )
        )
        return aes_key

    @staticmethod
    def decrypt_financial_offer(encrypted_file_bytes: bytes, aes_key: bytes, iv: bytes) -> bytes:
        """
        Déchiffre le fichier PDF (en mémoire) en utilisant la clé symétrique AES récupérée.
        """
        cipher = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
        decryptor = cipher.decryptor()
        
        decrypted_padded_file = decryptor.update(encrypted_file_bytes) + decryptor.finalize()
        
        # Remove PKCS7 padding
        # In this simple implementation, if the file has standard padding we remove it
        # (Assuming the client used PKCS7 padding)
        pad_len = decrypted_padded_file[-1]
        decrypted_file = decrypted_padded_file[:-pad_len]
        
        return decrypted_file
    
    @staticmethod
    def extract_montant(decrypted_pdf_bytes: bytes) -> float:
        """
        Extraction simulée du montant financier depuis le PDF déchiffré.
        """
        # (Mock implementation)
        # In reality this might use OCR, PDF parsing (PyPDF2, pdfplumber), or structured data embedded inside the PDF.
        return 1500000.00
