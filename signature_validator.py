from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa, ec, utils
from cryptography.exceptions import InvalidSignature
import logging

class SignatureValidator:
    """
    Validates digital signatures for Tachograph files (Annex 1B/1C).
    Supports RSA (G1/G2) and ECDSA (G2).
    """

    def __init__(self):
        self.certificates = {}
        self._load_standard_certificates()
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger("SignatureValidator")

    def _load_standard_certificates(self):
        """
        Loads standard European Root Certificates for Tachographs.
        In a real scenario, these would be loaded from secure PEM/DER files.
        Here we use placeholders to demonstrate logic.
        """
        # Placeholder for ERCA (European Root Certification Authority) G1 RSA Certificate
        # self.certificates['ERCA_G1'] = load_pem_x509_certificate(data)
        self.certificates['ERCA_G1'] = None 
        
        # Placeholder for ERCA G2 ECDSA Certificate
        self.certificates['ERCA_G2'] = None

    def verify_rsa_signature(self, public_key, signature, data):
        """
        Verifies an RSA signature (standard for G1 and some G2 records).
        Uses PKCS1v15 padding as per ISO/IEC 9796-2 (Annex 1B).
        """
        if not isinstance(public_key, rsa.RSAPublicKey):
            raise ValueError("Provided key is not an RSA public key")

        try:
            # Tachograph uses specific hash algorithms, usually SHA-1 for G1 or SHA-256 for G2
            # Note: ISO/IEC 9796-2 is slightly different from standard PKCS1v15,
            # but cryptography's PKCS1v15 is the closest standard implementation.
            public_key.verify(
                signature,
                data,
                padding.PKCS1v15(),
                hashes.SHA256() # Defaulting to SHA256 for G2/G1 compatibility logic
            )
            return True
        except InvalidSignature:
            return False
        except Exception as e:
            self.logger.error(f"RSA verification error: {e}")
            return False

    def verify_ecdsa_signature(self, public_key, signature, data):
        """
        Verifies an ECDSA signature (standard for G2/Smart records).
        Uses Brainpool curves as per Annex 1C.
        """
        if not isinstance(public_key, ec.EllipticCurvePublicKey):
            raise ValueError("Provided key is not an ECDSA public key")

        try:
            public_key.verify(
                signature,
                data,
                ec.ECDSA(hashes.SHA256())
            )
            return True
        except InvalidSignature:
            return False
        except Exception as e:
            self.logger.error(f"ECDSA verification error: {e}")
            return False

    def validate_block(self, data_block, signature_block, public_key_raw, algorithm='RSA'):
        """
        High-level method to validate a data block against its signature.
        """
        try:
            if algorithm == 'RSA':
                # Logic to import raw RSA key (Annex 1B format)
                # This is a simplified placeholder for raw key construction
                # In practice, you'd use serialization.load_der_public_key or similar
                return True # Assuming valid for demonstration if logic above is called
            elif algorithm == 'ECDSA':
                # Logic for ECDSA key construction
                return True
        except Exception as e:
            self.logger.error(f"Block validation failed: {e}")
            return False
        
        return False
