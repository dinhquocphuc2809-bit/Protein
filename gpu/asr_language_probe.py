"""Isolated reproduction of a fallback tokenizer language failure."""
import modal
from gpu.asr import Recognizer, image, weights

app = modal.App('vocalm-qwen-language-test')


@app.cls(image=image, gpu='T4', cpu=2, memory=16384, volumes={'/weights':weights},
         min_containers=0, max_containers=1, scaledown_window=10, timeout=240)
class Probe:
    @modal.enter()
    def load(self):
        cls = Recognizer._get_user_cls()
        self.engine = cls()
        cls.__dict__['load']._get_raw_f()(self.engine)

    @modal.method()
    def diagnose(self, wavs):
        original = self.engine.model.transcribe
        detected = []
        def capture(*args, **kwargs):
            rows = original(*args, **kwargs)
            detected.extend({'language':r.language,'characters':len(r.text),'text':r.text} for r in rows)
            return rows
        self.engine.model.transcribe = capture
        try:
            results = self.engine._transcribe_many(wavs, 'auto')
            return {'ok':True,'detected':detected,'results':results}
        except Exception as error:
            import traceback
            model = self.engine.whisper
            from whisper.tokenizer import LANGUAGES
            return {'ok':False,'detected':detected,'error_type':type(error).__name__,
                    'error':str(error), 'traceback':traceback.format_exc(),
                    'whisper_num_languages':model.num_languages if model else None,
                    'yue_supported':model is not None and 'yue' in tuple(LANGUAGES)[:model.num_languages]}
        finally:
            self.engine.model.transcribe = original
