import rename_images


def test_slugify_transliterates_russian_text():
    assert rename_images.slugify("Платежное поручение") == "platezhnoe_poruchenie"


def test_slugify_strips_stop_words():
    assert rename_images.slugify("Форма — нажмите кнопку Подтвердить") == "forma"


def test_slugify_strips_leading_junk():
    assert rename_images.slugify("— Список счетов") == "spisok_schetov"
