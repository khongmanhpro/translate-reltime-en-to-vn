"""🌐 Translation module: DeepL API + Argos Translate fallback."""

import json
import urllib.request
import urllib.parse
from typing import Optional
from loguru import logger
from config import DEEPL_API_KEY, DEEPL_API_URL, TARGET_LANG, USE_ARGOS_FALLBACK


class DeepLTranslator:
    """Translate text using DeepL API (free tier: 500K chars/month)."""

    def __init__(self, api_key: str = DEEPL_API_KEY, target_lang: str = TARGET_LANG):
        self.api_key = api_key
        self.target_lang = target_lang
        self.api_url = DEEPL_API_URL

    def translate(self, text: str) -> Optional[str]:
        if not self.api_key:
            logger.warning("⚠️ DeepL API key not set")
            return None
        try:
            data = urllib.parse.urlencode({
                "auth_key": self.api_key,
                "text": text,
                "target_lang": self.target_lang,
            }).encode("utf-8")

            req = urllib.request.Request(self.api_url, data=data, method="POST")
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
                translated = result.get("translations", [{}])[0].get("text", "")
                if translated:
                    logger.debug(f"🌐 DeepL: {text[:50]}... → {translated[:50]}...")
                return translated
        except Exception as e:
            logger.error(f"❌ DeepL error: {e}")
            return None


class GoogleTranslateAPI:
    """Lightweight API fallback using Google Translate web endpoint."""

    def __init__(self, target_lang: str = TARGET_LANG, source_lang: str = "en"):
        self.target_lang = target_lang.lower()
        self.source_lang = source_lang
        self.api_url = "https://translate.googleapis.com/translate_a/single"

    def translate(self, text: str) -> Optional[str]:
        try:
            params = urllib.parse.urlencode({
                "client": "gtx",
                "sl": self.source_lang,
                "tl": self.target_lang,
                "dt": "t",
                "q": text,
            })
            req = urllib.request.Request(f"{self.api_url}?{params}", method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read().decode("utf-8"))
            translated = "".join(part[0] for part in result[0] if part and part[0]).strip()
            if translated:
                logger.debug(f"🌐 Google: {text[:50]}... → {translated[:50]}...")
            return translated or None
        except Exception as e:
            logger.error(f"❌ Google translate error: {e}")
            return None


class ArgosTranslator:
    """Offline translation using Argos Translate."""

    def __init__(self, from_code: str = "en", to_code: str = "vi"):
        self.from_code = from_code
        self.to_code = to_code
        self._translator = None
        self._load()

    def _load(self):
        try:
            import argostranslate.package
            import argostranslate.translate

            # Install en→vi package if not present
            installed = argostranslate.translate.get_installed_languages()
            from_lang = next((l for l in installed if l.code == self.from_code), None)
            to_lang = next((l for l in installed if l.code == self.to_code), None)

            if not from_lang or not to_lang:
                logger.info("📦 Installing Argos en→vi translation package...")
                argostranslate.package.update_package_index()
                available = argostranslate.package.get_available_packages()
                pkg = next(
                    (p for p in available
                     if p.from_code == self.from_code and p.to_code == self.to_code),
                    None
                )
                if pkg:
                    download_path = pkg.download()
                    argostranslate.package.install_from_path(download_path)
                    installed = argostranslate.translate.get_installed_languages()
                    from_lang = next((l for l in installed if l.code == self.from_code), None)
                    to_lang = next((l for l in installed if l.code == self.to_code), None)

            if from_lang and to_lang:
                self._translator = from_lang.get_translation(to_lang)
                logger.info("✅ Argos Translate en→vi loaded")
            else:
                logger.warning("⚠️ Argos: en→vi package not available")
        except Exception as e:
            logger.warning(f"⚠️ Argos init failed: {e}")

    def translate(self, text: str) -> Optional[str]:
        if not self._translator:
            return None
        try:
            return self._translator.translate(text)
        except Exception as e:
            logger.error(f"❌ Argos error: {e}")
            return None


class TextTranslator:
    """Combined translator with DeepL primary + Argos fallback."""

    def __init__(self, target_lang: str = TARGET_LANG):
        self.deepl = DeepLTranslator(target_lang=target_lang)
        self.google = GoogleTranslateAPI(target_lang=target_lang)
        self.argos = None
        self.use_argos_fallback = USE_ARGOS_FALLBACK
        self.mode = "deepl" if DEEPL_API_KEY else "google-api"
        logger.info(f"🌐 Translator mode: {self.mode}")

    def translate(self, text: str) -> Optional[str]:
        if not text.strip():
            return None

        # Try DeepL first
        if DEEPL_API_KEY:
            result = self.deepl.translate(text)
            if result:
                return result

        # Lightweight API fallback, no local model.
        result = self.google.translate(text)
        if result:
            return result

        # Fallback to Argos
        if self.use_argos_fallback:
            if self.argos is None:
                self.argos = ArgosTranslator(to_code="vi")
            result = self.argos.translate(text)
            if result:
                return result

        logger.warning("⚠️ All translation methods failed")
        return None
