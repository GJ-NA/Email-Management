import pathlib
import unittest


ROOT_DIR = pathlib.Path(__file__).resolve().parents[1]


class TxtImportFrontendTests(unittest.TestCase):
    def test_import_modal_exposes_txt_file_picker(self):
        html = (ROOT_DIR / 'templates/partials/index/dialogs-primary.html').read_text(encoding='utf-8')

        self.assertIn('id="accountTxtFile"', html)
        self.assertIn('accept=".txt,text/plain"', html)
        self.assertIn('handleAccountTxtFileChange(event)', html)
        self.assertIn('选择 TXT 文件', html)

    def test_txt_file_handler_reads_text_and_resets_with_modal(self):
        js = (ROOT_DIR / 'static/js/index/07-settings.js').read_text(encoding='utf-8')

        self.assertIn('function decodeAccountTxtFile', js)
        self.assertIn('new TextDecoder(encoding)', js)
        self.assertIn("new TextDecoder('gb18030')", js)
        self.assertIn('function handleAccountTxtFileChange', js)
        self.assertIn('resetAccountTxtFileState();', js)
        self.assertIn('function clearAccountTxtFile', js)

    def test_txt_file_picker_has_responsive_styles(self):
        css = (ROOT_DIR / 'static/css/index/06-modals-toast.css').read_text(encoding='utf-8')

        self.assertIn('.import-account-file-picker', css)
        self.assertIn('.import-account-file-button', css)
        self.assertIn('.import-account-file-input', css)


if __name__ == '__main__':
    unittest.main()
