"""
Cloudinary Integration Test
Run: python test_cloudinary.py
Tests: config, upload, URL resolution, _save_photo logic, cleanup
"""

import os
import sys
import io
import json
import traceback

# Load .env manually (no Django needed)
def load_env(path='.env'):
    if not os.path.exists(path):
        print("[WARN] .env not found at " + path)
        return
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, _, val = line.partition('=')
            os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))

load_env()

RESULTS = []

def ok(msg):
    print("  [PASS]  " + msg)

def fail(msg):
    print("  [FAIL]  " + msg)

def warn(msg):
    print("  [WARN]  " + msg)

def section(title):
    print("\n" + "-" * 55)
    print("  " + title)
    print("-" * 55)

def record(name, passed, detail=''):
    RESULTS.append({'name': name, 'passed': passed, 'detail': detail})
    suffix = ("  ->  " + str(detail)) if detail else ''
    if passed:
        ok(name + suffix)
    else:
        fail(name + suffix)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 1 - Environment Variables
# ─────────────────────────────────────────────────────────────────────────────
section("1. Environment Variables")

CLOUD_NAME = os.environ.get('CLOUDINARY_CLOUD_NAME', '')
API_KEY    = os.environ.get('CLOUDINARY_API_KEY', '')
API_SECRET = os.environ.get('CLOUDINARY_API_SECRET', '')

record("CLOUDINARY_CLOUD_NAME set", bool(CLOUD_NAME), CLOUD_NAME or 'MISSING')
record("CLOUDINARY_API_KEY set",    bool(API_KEY),    (API_KEY[:6] + '...') if API_KEY else 'MISSING')
record("CLOUDINARY_API_SECRET set", bool(API_SECRET), (API_SECRET[:4] + '...') if API_SECRET else 'MISSING')

if CLOUD_NAME.endswith('"') or CLOUD_NAME.endswith("'"):
    record("No trailing quote in CLOUD_NAME", False, "value='" + CLOUD_NAME + "'")
else:
    record("No trailing quote in CLOUD_NAME", True)

if API_KEY.endswith('"') or API_SECRET.endswith('"'):
    record("No trailing quotes in KEY/SECRET", False, "Check .env for stray quotes")
else:
    record("No trailing quotes in KEY/SECRET", True)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 2 - Package Import
# ─────────────────────────────────────────────────────────────────────────────
section("2. Package Import")

try:
    import cloudinary
    import cloudinary.uploader
    import cloudinary.api
    version = getattr(cloudinary, '__version__', getattr(cloudinary, 'VERSION', 'unknown'))
    record("import cloudinary", True, "version " + str(version))
except ImportError as e:
    record("import cloudinary", False, str(e))
    print("\nCannot continue without cloudinary package.")
    print("Run:  pip install cloudinary")
    sys.exit(1)


# ─────────────────────────────────────────────────────────────────────────────
# TEST 3 - Cloudinary Configuration
# ─────────────────────────────────────────────────────────────────────────────
section("3. Cloudinary Configuration")

try:
    cloudinary.config(
        cloud_name=CLOUD_NAME,
        api_key=API_KEY,
        api_secret=API_SECRET,
        secure=True,
    )
    cfg = cloudinary.config()
    record("cloudinary.config() applied", True)
    record("cloud_name matches env",      cfg.cloud_name == CLOUD_NAME, str(cfg.cloud_name))
    record("api_key matches env",         cfg.api_key == API_KEY,       (cfg.api_key[:6] + '...') if cfg.api_key else 'None')
    record("api_secret set",              bool(cfg.api_secret),         '(hidden)')
    record("secure=True",                 cfg.secure == True)
except Exception as e:
    record("cloudinary.config()", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# TEST 4 - Ping Cloudinary API
# ─────────────────────────────────────────────────────────────────────────────
section("4. Cloudinary API Connectivity (ping)")

try:
    result = cloudinary.api.ping()
    record("API ping successful", result.get('status') == 'ok', json.dumps(result))
except Exception as e:
    record("API ping", False, str(e))
    warn("Credentials may be wrong or network is blocked.")


# ─────────────────────────────────────────────────────────────────────────────
# TEST 5 - Upload a minimal test image
# ─────────────────────────────────────────────────────────────────────────────
section("5. Upload Test Image")

# 1x1 red pixel PNG — valid minimal PNG, no external file needed
MINIMAL_PNG = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00'
    b'\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18'
    b'\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
)

uploaded_public_id  = None
uploaded_secure_url = None

try:
    image_file = io.BytesIO(MINIMAL_PNG)
    image_file.name = 'test_pixel.png'

    result = cloudinary.uploader.upload(
        image_file,
        folder='student_photos/test',
        public_id='test_cloudinary_integration',
        overwrite=True,
        resource_type='image',
    )

    uploaded_public_id  = result.get('public_id')
    uploaded_secure_url = result.get('secure_url')
    fmt    = result.get('format', '')
    width  = result.get('width', 0)
    height = result.get('height', 0)

    record("Upload succeeded",        True)
    record("public_id returned",      bool(uploaded_public_id),  uploaded_public_id or 'MISSING')
    record("secure_url returned",     bool(uploaded_secure_url), uploaded_secure_url or 'MISSING')
    record("secure_url is https",     (uploaded_secure_url or '').startswith('https://'), uploaded_secure_url)
    record("format is png",           fmt == 'png', fmt)
    record("dimensions 1x1",          width == 1 and height == 1, str(width) + "x" + str(height))

except Exception as e:
    record("Upload test image", False, str(e))
    traceback.print_exc()


# ─────────────────────────────────────────────────────────────────────────────
# TEST 6 - Simulate _save_photo logic
# ─────────────────────────────────────────────────────────────────────────────
section("6. Simulate _save_photo Logic")

class FakeStudent:
    """Minimal stand-in for a Student model instance."""
    id = 9999
    photo = None
    _saved = False
    _update_fields = None

    def save(self, update_fields=None):
        self._saved = True
        self._update_fields = update_fields

def simulate_save_photo(instance, photo_file):
    """Exact copy of StudentSerializer._save_photo for isolated testing."""
    result = cloudinary.uploader.upload(
        photo_file,
        folder='student_photos',
        public_id='student_' + str(instance.id),
        overwrite=True,
        resource_type='image',
    )
    instance.photo = result.get('public_id') or result.get('secure_url')
    instance.save(update_fields=['photo'])
    return result

try:
    fake = FakeStudent()
    image_file = io.BytesIO(MINIMAL_PNG)
    image_file.name = 'student_test.png'

    result = simulate_save_photo(fake, image_file)

    record("_save_photo: upload succeeded",        True)
    record("_save_photo: instance.photo set",      bool(fake.photo), fake.photo or 'NOT SET')
    record("_save_photo: instance.save() called",  fake._saved)
    record("_save_photo: update_fields=['photo']", fake._update_fields == ['photo'], str(fake._update_fields))

    photo_str = str(fake.photo or '')
    is_valid_ref = (
        'student_photos/student_9999' in photo_str or
        photo_str.startswith('https://')
    )
    record("_save_photo: photo is valid public_id or URL", is_valid_ref, photo_str)

except Exception as e:
    record("_save_photo simulation", False, str(e))
    traceback.print_exc()


# ─────────────────────────────────────────────────────────────────────────────
# TEST 7 - URL resolution (get_photo logic)
# ─────────────────────────────────────────────────────────────────────────────
section("7. URL Resolution (get_photo logic)")

def simulate_get_photo(photo_value):
    """Exact copy of StudentSerializer.get_photo for isolated testing."""
    if not photo_value:
        return None
    try:
        if hasattr(photo_value, 'url'):
            url = photo_value.url
        else:
            val = str(photo_value)
            if val.startswith('http'):
                url = val
            else:
                url = cloudinary.CloudinaryImage(val).build_url(secure=True)

        if url and (url.startswith('http://') or url.startswith('https://')):
            return url
        return 'http://localhost:8000' + url
    except Exception:
        return None

cases = [
    (None,                                         None,  "None input -> None"),
    ('',                                           None,  "Empty string -> None"),
    ('https://res.cloudinary.com/x/image/y.jpg',  True,  "Absolute https URL -> returned as-is"),
    ('http://localhost/media/photo.jpg',           True,  "Absolute http URL -> returned as-is"),
    ('student_photos/student_1',                   True,  "Cloudinary public_id -> builds URL"),
]

for photo_val, expect_truthy, label in cases:
    res = simulate_get_photo(photo_val)
    if expect_truthy is None:
        passed = res is None
    else:
        passed = bool(res) == expect_truthy
    record(label, passed, repr(res))


# ─────────────────────────────────────────────────────────────────────────────
# TEST 8 - Cleanup uploaded test assets
# ─────────────────────────────────────────────────────────────────────────────
section("8. Cleanup Test Assets")

ids_to_delete = [
    'student_photos/test/test_cloudinary_integration',
    'student_photos/student_9999',
]

for pid in ids_to_delete:
    try:
        res = cloudinary.uploader.destroy(pid, resource_type='image')
        deleted = res.get('result') in ('ok', 'not found')
        record("Delete '" + pid + "'", deleted, res.get('result', ''))
    except Exception as e:
        record("Delete '" + pid + "'", False, str(e))


# ─────────────────────────────────────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────────────────────────────────────
section("SUMMARY")

passed_list = [r for r in RESULTS if r['passed']]
failed_list = [r for r in RESULTS if not r['passed']]

print("\n  Total : " + str(len(RESULTS)))
print("  Passed: " + str(len(passed_list)))
print("  Failed: " + str(len(failed_list)))

if failed_list:
    print("\n  Failed tests:")
    for r in failed_list:
        print("    [FAIL]  " + r['name'])
        if r['detail']:
            print("            " + r['detail'])

if not failed_list:
    print("\n  All tests passed! Cloudinary is configured correctly.")
    print("  Photos upload to: https://res.cloudinary.com/" + CLOUD_NAME + "/image/upload/student_photos/")
else:
    print("\n  Fix the failed tests above before deploying.")

print()
sys.exit(0 if not failed_list else 1)
