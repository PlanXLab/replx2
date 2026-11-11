"""cryptolib - symmetric crypto primitives.

This module typically provides AES block cipher support.

Notes
-----
- This is a low-level primitive: it does not provide padding schemes.
    For ECB/CBC you must supply data in 16-byte blocks.
- Mode availability and exact semantics may vary by port.
- Correct IV/counter handling is critical for security.

Example
-------
```python
    >>> import cryptolib
    >>> 
    >>> # AES-128 ECB encryption
    >>> key = b'\\x00' * 16
    >>> cipher = cryptolib.aes(key, 1)  # ECB mode
    >>> encrypted = cipher.encrypt(b'\\x00' * 16)
```
"""

from typing import Union


class aes:
    """
    AES cipher object.

    Modes:
    - 1: ECB (Electronic Code Book)
    - 2: CBC (Cipher Block Chaining)
    - 6: CTR (Counter)

    Example
    -------
    ```python
        >>> import cryptolib
        >>> 
        >>> key = b'1234567890123456'  # 16 bytes for AES-128
        >>> 
        >>> # ECB mode
        >>> cipher = cryptolib.aes(key, 1)
        >>> encrypted = cipher.encrypt(b'Hello World!!!!!')
        >>> 
        >>> # CBC mode with IV
        >>> iv = b'\\x00' * 16
        >>> cipher = cryptolib.aes(key, 2, iv)
        >>> encrypted = cipher.encrypt(b'Hello World!!!!!')
    ```
    """

    def __init__(self, key: bytes, mode: int, iv: bytes = None) -> None:
        """
        Create AES cipher.

        :param key: 16, 24, or 32 bytes (AES-128/192/256)
        :param mode: 1=ECB, 2=CBC, 6=CTR
        :param iv: Initialization vector for CBC/CTR (16 bytes)

        Example
        -------
        ```python
            >>> import cryptolib
            >>> 
            >>> # AES-128 ECB
            >>> cipher = cryptolib.aes(b'\\x00' * 16, 1)
            >>> 
            >>> # AES-256 CBC
            >>> key = b'\\x00' * 32
            >>> iv = b'\\x00' * 16
            >>> cipher = cryptolib.aes(key, 2, iv)
        ```
        """
        ...

    def encrypt(self, data: Union[bytes, bytearray]) -> bytes:
        """Encrypt data.

        For ECB/CBC, `data` must be a multiple of 16 bytes.
        For CTR, ports may accept arbitrary lengths.

        :param data: Plaintext (16-byte aligned)

        :returns: Ciphertext

        Example
        -------
        ```python
            >>> import cryptolib
            >>> 
            >>> cipher = cryptolib.aes(b'\\x00' * 16, 1)
            >>> ciphertext = cipher.encrypt(b'\\x00' * 16)
            >>> print(ciphertext.hex())
        ```
        """
        ...

    def decrypt(self, data: Union[bytes, bytearray]) -> bytes:
        """
        Decrypt data block(s).

        :param data: Ciphertext (16-byte aligned)

        :returns: Plaintext

        Example
        -------
        ```python
            >>> import cryptolib
            >>> 
            >>> cipher = cryptolib.aes(b'\\x00' * 16, 1)
            >>> plaintext = cipher.decrypt(ciphertext)
        ```
        """
        ...
