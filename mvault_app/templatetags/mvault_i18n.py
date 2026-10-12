import re
from django import template
from django.urls import reverse
from django.utils.html import format_html
import hashlib
from ..locales import TABLES
from ..storage import avatar_public_url, icon_public_url

register = template.Library()

ICONS = {
    "grid", "folder", "users", "clock", "cog", "logout", "plus", "key", "card",
    "code", "trash", "pencil", "share", "eye", "eye-off", "clipboard", "upload", "download",
    "check", "x", "user-plus", "user-minus", "lock", "arrow-left", "arrow-right",
    "shield", "server", "database", "globe", "briefcase", "star", "home", "cloud", "bolt", "menu",
    "chevron-right", "chevron-down", "braces", "file",
}

ACTIVITY_LABELS = {
    "login": "Signed in", "logout": "Signed out", "password_changed": "Changed password",
    "member_created": "Created member account", "member_deactivated": "Deactivated member",
    "member_activated": "Activated member", "member_password_reset": "Reset member password",
    "member_deleted": "Deleted member account", "project_created": "Created project",
    "project_updated": "Updated project", "project_deleted": "Deleted project",
    "project_shared": "Shared project", "folder_created": "Created folder",
    "folder_updated": "Updated folder", "folder_deleted": "Deleted folder",
    "record_created": "Created record", "record_updated": "Updated record",
    "record_deleted": "Deleted record", "record_imported": "Imported record",
    "record_import_updated": "Updated imported record", "record_copied": "Copied record",
    "record_shared": "Shared record", "shared_record_viewed": "Viewed shared record",
    "value_reveal": "Revealed value", "value_copy": "Copied value",
    "env_exported": "Exported environment file", "file_downloaded": "Downloaded file", "data_exported": "Exported all data",
}


@register.simple_tag
def icon(name):
    if name not in ICONS:
        return ""
    return format_html(
        '<svg class="icon" aria-hidden="true" focusable="false"><use href="#mv-icon-{}"></use></svg>',
        name,
    )


@register.simple_tag
def avatar(user):
    """Round avatar: the uploaded picture, else the Gravatar if one exists, else initials.

    Initials are always rendered underneath; the picture is an overlay that removes itself when it fails
    to load (Gravatar answers 404 for unknown addresses), which reveals the initials.
    """
    initials = format_html('<span class="avatar-initials">{}</span>', user.initials)
    if user.avatar_key:
        src = avatar_public_url(user.avatar_key)
    else:
        digest = hashlib.sha256(user.email.strip().lower().encode()).hexdigest()
        src = f"https://gravatar.com/avatar/{digest}?s=96&d=404"
    return format_html('<div class="avatar">{}<img class="avatar-img" alt="" referrerpolicy="no-referrer" loading="lazy" src="{}" onerror="this.remove()"></div>', initials, src)


@register.simple_tag
def entity_icon(obj):
    """Icon for a project or folder: the uploaded image when present, otherwise the built-in glyph."""
    key = getattr(obj, "custom_icon_key", "")
    if key:
        return format_html('<img class="icon icon-image" alt="" loading="lazy" decoding="async" src="{}">', icon_public_url(key))
    return icon(obj.icon)


@register.inclusion_tag("mvault/breadcrumbs.html", takes_context=True)
def breadcrumbs(context):
    request = context.get("request")
    if request is None:
        return {"items": []}
    # The inclusion template gets only the returned dict, and ``tr`` needs the request to know the language.
    items_context = {"request": request}

    view = getattr(request.resolver_match, "url_name", "")
    user = request.user
    items = []

    def add(label, url=None):
        items.append({"label": label, "url": url})

    def dashboard_link():
        add("Dashboard", reverse("dashboard"))

    if not user.is_authenticated:
        add("Sign in")
        return {"items": items, **items_context}

    if user.is_admin and view in {"admin_dashboard", "member_create", "member_password", "member_delete"}:
        if view == "admin_dashboard":
            add("Member accounts")
        else:
            add("Member accounts", reverse("admin_dashboard"))
            member = context.get("member")
            if member is not None:
                add(member.full_name, reverse("admin_dashboard"))
            add({
                "member_create": "Add a member",
                "member_password": "Reset password",
                "member_delete": "Delete member",
            }[view])
        return {"items": items, **items_context}

    if view == "dashboard":
        add("Dashboard")
        return {"items": items, **items_context}

    if view == "password_change_required":
        add("Choose a new password")
        return {"items": items, **items_context}

    project = context.get("project")
    folder = context.get("folder")
    record = context.get("record")
    shared_object = context.get("object") if view == "share_create" else None

    if view == "share_create" and context.get("kind") == "project":
        project = shared_object
    elif view == "share_create" and context.get("kind") == "record":
        record = shared_object

    if record is not None:
        project = project or record.project
        folder = folder or record.folder

    if context.get("readonly") and view in {"project_detail", "folder_detail", "record_detail"}:
        dashboard_link()
        add("Shared with me", reverse("shared_items"))
        if view == "project_detail" and project is not None:
            add(project.name)
        elif view == "folder_detail" and folder is not None:
            if project is not None:
                add(project.name, reverse("project_detail", args=[project.pk]))
            add(folder.name)
        elif view == "record_detail" and record is not None:
            from ..models import ProjectShare
            if project is not None and ProjectShare.objects.filter(
                project=project, recipient=user, revoked_at__isnull=True, project__owner__is_active=True,
            ).exists():
                add(project.name, reverse("project_detail", args=[project.pk]))
                if folder is not None:
                    add(folder.name, reverse("folder_detail", args=[folder.pk]))
            add(record.name)
        return {"items": items, **items_context}

    dashboard_link()

    if view == "admin_dashboard":
        add("Member accounts")
    elif view in {"member_create", "member_password", "member_delete"}:
        add("Administration", reverse("admin_dashboard"))
        add("Member accounts", reverse("admin_dashboard"))
        member = context.get("member")
        if member is not None:
            add(member.full_name, reverse("admin_dashboard"))
        add({"member_create": "Add a member", "member_password": "Reset password", "member_delete": "Delete member"}[view])
    elif view == "settings":
        add("Settings")
    elif view in {"password_change", "password_change_required"}:
        if view == "password_change":
            add("Settings", reverse("settings"))
            add("Change password")
    elif view == "audit_log":
        add("Activity")
    elif view == "shared_items":
        add("Shared with me")
    elif view == "record_copy":
        add("Shared with me", reverse("shared_items"))
        if record is not None:
            add(record.name, reverse("record_detail", args=[record.pk]))
        add("Copy shared record")
    elif view == "project_create":
        add("Create a project")
    elif project is not None:
        project_is_current = view == "project_detail"
        add(project.name, None if project_is_current else reverse("project_detail", args=[project.pk]))

        if view == "project_edit":
            add("Edit project")
        elif view == "folder_create":
            add("Create a folder")
        elif folder is not None:
            folder_is_current = view == "folder_detail"
            add(folder.name, None if folder_is_current else reverse("folder_detail", args=[folder.pk]))

            if view == "folder_edit":
                add("Edit folder")
            elif view in {"record_create_in_folder", "record_create"}:
                add("Add a record")
            elif record is not None:
                record_is_current = view == "record_detail"
                add(record.name, None if record_is_current else reverse("record_detail", args=[record.pk]))
                if view == "record_edit":
                    add("Edit record")
                elif view == "record_history":
                    add("History")
                elif view == "share_create":
                    add("Share")
            elif view == "share_create":
                add("Share")
        elif view in {"record_create", "record_create_in_folder"}:
            add("Add a record")
        elif view == "share_create":
            add("Share")

    return {"items": items, **items_context}

RU = {
    "Choose a record type, then fill in its details.": "Выберите тип записи и заполните данные.", "The record type cannot be changed.": "Тип записи изменить нельзя.",
    "Avatar": "Аватар", "Upload avatar": "Загрузить аватар", "Remove avatar": "Удалить аватар", "Avatar updated.": "Аватар обновлён.", "Avatar removed.": "Аватар удалён.",
    "Choose an image to upload.": "Выберите изображение для загрузки.", "Avatars must be 2 MB or smaller.": "Размер аватара не должен превышать 2 МБ.",
    "Avatars must be PNG, JPEG, WebP, or GIF images.": "Аватар должен быть изображением PNG, JPEG, WebP или GIF.",
    "Your uploaded picture is shown first. Without one, your Gravatar for this email is used, and then your initials.": "Сначала показывается загруженное фото. Если его нет — Gravatar для вашей почты, затем инициалы.",
    "PNG, JPEG, WebP, or GIF up to 2 MB. It is cropped to a square.": "PNG, JPEG, WebP или GIF до 2 МБ. Изображение обрезается до квадрата.",
    "Export all data": "Экспорт всех данных", "Exported all data": "Экспортированы все данные",
    "Download a ZIP with all your projects and folders as directories, a CSV with decrypted values in each, and file records as the original files. Keep it somewhere safe: it contains your secrets in plain text.": "Скачайте ZIP-архив: проекты и папки в виде каталогов, в каждом CSV с расшифрованными значениями, а файловые записи — в виде исходных файлов. Храните его надёжно: в нём ваши секреты в открытом виде.",
    "JSON": "JSON", "Files": "Файлы", "File": "Файл", "Download": "Скачать", "Downloaded file": "Скачан файл",
    "Format": "Форматировать", "Minify": "Сжать", "Valid JSON": "Корректный JSON",
    "Current file": "Текущий файл", "Choose a new file to replace it.": "Выберите новый файл, чтобы заменить его.",
    "File (max 50 MB)": "Файл (макс. 50 МБ)", "Choose a file to upload.": "Выберите файл для загрузки.",
    "Files must be 50 MB or smaller.": "Размер файла не должен превышать 50 МБ.", "Enter a JSON document.": "Введите JSON-документ.",
    "Custom icon": "Своя иконка", "Remove custom icon": "Удалить свою иконку", "optional, replaces the icon above": "необязательно, заменяет иконку выше",
    "PNG, JPEG, WebP, or GIF up to 2 MB. It is resized to 128 px.": "PNG, JPEG, WebP или GIF до 2 МБ. Размер будет уменьшен до 128 px.",
    "Icons must be 2 MB or smaller.": "Размер иконки не должен превышать 2 МБ.", "That file is not a valid image.": "Этот файл не является изображением.",
    "Icons must be PNG, JPEG, WebP, or GIF images.": "Иконки должны быть изображениями PNG, JPEG, WebP или GIF.",
    "The file could not be retrieved from storage.": "Не удалось получить файл из хранилища.",
    "Dashboard": "Главная",
    "Your projects": "Ваши проекты",
    "Shared with me": "Мне предоставлен доступ",
    "Activity": "Активность",
    "Settings": "Настройки",
    "Log out": "Выйти",
    "Administrator": "Администратор",
    "Member": "Участник",
    "Welcome back": "С возвращением",
    "Sign in to access your family vault.": "Войдите, чтобы открыть семейное хранилище.",
    "Sign in": "Войти",
    "Personal vault": "Личное хранилище",
    "Your vault": "Ваше хранилище",
    "Everything you keep, organized by project.": "Все ваши данные, сгруппированные по проектам.",
    "New project": "Новый проект",
    "Active projects": "Активные проекты",
    "Records across projects": "Записи во всех проектах",
    "Recent activity events": "Последние события",
    "Projects": "Проекты",
    "Latest activity": "Последние действия",
    "View all activity →": "Вся активность →",
    "Records by project and type": "Записи по проектам и типам",
    "No projects yet.": "Пока нет проектов.",
    "Activity will appear here.": "Здесь появится история действий.",
    "No records": "Нет записей",
    "No folders yet.": "Пока нет папок.",
    "No records in this project.": "В этом проекте пока нет записей.",
    "This folder is empty.": "Папка пуста.",
    "No activity recorded.": "Действий пока нет.",
    "Member accounts": "Учетные записи участников",
    "Manage access and account lifecycle.": "Управление доступом и учетными записями.",
    "Add member": "Добавить участника",
    "No members have been created.": "Участники еще не добавлены.",
    "Active": "Активен",
    "Deactivated": "Отключен",
    "Deactivate": "Отключить",
    "Activate": "Включить",
    "Reset password": "Сбросить пароль",
    "Delete": "Удалить",
    "Member management activity": "Действия с учетными записями",
    "No recent account events.": "Недавних событий нет.",
    "Administration": "Администрирование",
    "Create an account for a family member.": "Создайте учетную запись для члена семьи.",
    "Members cannot sign themselves up.": "Участники не могут зарегистрироваться самостоятельно.",
    "Use strong password": "Сгенерировать надежный пароль",
    "The member will need to change this password at first sign-in.": "Участнику нужно будет сменить этот пароль при первом входе.",
    "Create member": "Создать учетную запись",
    "Set temporary password": "Задать временный пароль",
    "The member must change it at next sign-in.": "Участник должен сменить его при следующем входе.",
    "Permanent action": "Необратимое действие",
    "This cannot be undone. Choose what happens to their projects and records.": "Это действие нельзя отменить. Выберите, что сделать с проектами и записями.",
    "Transfer projects and records to another active member": "Передать проекты и записи другому активному участнику",
    "Permanently purge projects, records, and record history": "Удалить проекты, записи и историю без возможности восстановления",
    "Live shares are revoked. Copies held by other members remain their own records.": "Общий доступ будет отозван. Копии других участников останутся у них.",
    "Delete account": "Удалить учетную запись",
    "Cancel": "Отмена",
    "Account security": "Безопасность учетной записи",
    "Choose a new password": "Задайте новый пароль",
    "Change password": "Сменить пароль",
    "Your administrator assigned this password. Change it before continuing.": "Администратор назначил этот пароль. Смените его, чтобы продолжить.",
    "Use a strong password that you do not use elsewhere.": "Используйте надежный пароль, который вы больше нигде не применяете.",
    "Update password": "Обновить пароль",
    "Your account": "Ваша учетная запись",
    "Update your profile and language.": "Измените профиль и язык интерфейса.",
    "Full name": "Полное имя",
    "Email": "Электронная почта",
    "Preferred language": "Язык интерфейса",
    "English": "Английский",
    "Save settings": "Сохранить настройки",
    "Vault organization": "Структура хранилища",
    "Edit project": "Изменить проект",
    "Create a project": "Создать проект",
    "Projects are private unless you share them.": "Проекты доступны только вам, пока вы ими не поделитесь.",
    "Save project": "Сохранить проект",
    "Delete this project and hide its records? Their history will be retained.": "Удалить проект и скрыть записи? История записей сохранится.",
    "Delete project": "Удалить проект",
    "Environment": "Среда",
    "Folder": "Папка",
    "Edit folder": "Изменить папку",
    "Create a folder": "Создать папку",
    "Folders sit directly under a project.": "Папки находятся непосредственно в проекте.",
    "Common environment names": "Популярные названия сред",
    "Choose a preset…": "Выберите вариант…",
    "Save folder": "Сохранить папку",
    "Delete this folder and hide its records?": "Удалить папку и скрыть ее записи?",
    "Delete folder": "Удалить папку",
    "Add record": "Добавить запись",
    "Add folder": "Добавить папку",
    "Share": "Поделиться",
    "Edit": "Изменить",
    "Project vault": "Хранилище проекта",
    "Shared read-only": "Общий доступ · только чтение",
    "Records in project": "Записи проекта",
    "Read-only access": "Доступ только для чтения",
    "Shared by": "Поделился",
    "Updated": "Обновлено",
    "History": "История",
    "Copy to my vault": "Скопировать в мое хранилище",
    "Enter a valid card number (12-19 digits).": "Введите корректный номер карты (12–19 цифр).",
    "Enter the expiry date as MM/YY.": "Введите срок действия в формате ММ/ГГ.",
    "Enter a valid CVV (3 digits, 4 for American Express).": "Введите корректный CVV (3 цифры, 4 для American Express).",
    "PIN must be 4 to 12 digits.": "PIN-код должен содержать от 4 до 12 цифр.",
    "Reveal": "Показать",
    "Hide": "Скрыть",
    "Copy": "Копировать",
    "Copied": "Скопировано",
    "No active shares.": "Нет активных ссылок общего доступа.",
    "Revoke": "Отозвать",
    "Delete this record? Its history will remain available.": "Удалить запись? Ее история останется доступна.",
    "Delete record": "Удалить запись",
    "Changes are kept in record history for the owner.": "Владелец может просмотреть изменения в истории записи.",
    "Record revisions": "Версии записи",
    "Change history": "История изменений",
    "Previous values remain readable to you as the record owner.": "Как владелец записи, вы можете просматривать предыдущие значения.",
    "No revisions available.": "Истории изменений пока нет.",
    "Audit log": "Журнал действий",
    "Your activity": "Ваши действия",
    "Actions on your vault and shared records are listed here.": "Здесь перечислены действия в вашем хранилище и общих записях.",
    "Newer": "Новее",
    "Older": "Старее",
    "Independent copy": "Независимая копия",
    "Choose a project. The copy belongs to you and will not change when the owner edits their record.": "Выберите проект. Копия будет принадлежать вам и не изменится, если владелец изменит оригинал.",
    "Destination project": "Проект назначения",
    "No projects available": "Нет доступных проектов",
    "Create independent copy": "Создать независимую копию",
    "Import environment variables": "Импорт переменных окружения",
    "Existing keys are updated in place. Sensitive-looking keys default to Secret.": "Существующие ключи будут обновлены. Похожие на секреты ключи по умолчанию помечаются как секретные.",
    "Import file": "Импортировать файл",
    "Export .env": "Экспортировать .env",
    "Import .env": "Импортировать .env",
    "Secrets": "Секреты",
    "Passwords": "Пароли",
    "Bank Cards": "Банковские карты",
    "Password": "Пароль",
    "Bank card": "Банковская карта",
    "Environment / secret variable": "Переменная окружения / секрет",
    "Title / key": "Название / ключ",
    "Username": "Имя пользователя",
    "Website": "Сайт",
    "Notes": "Заметки",
    "Cardholder": "Держатель карты",
    "Number": "Номер",
    "Expiration": "Срок действия",
    "CVV": "CVV",
    "Issuer": "Банк / эмитент",
    "PIN": "PIN-код",
    "Value": "Значение",
    "Value type": "Тип значения",
    "Variable key": "Ключ переменной",
    "Secret": "Секрет",
    "Plain": "Обычный текст",
    "Save record": "Сохранить запись",
    "Add a record": "Добавить запись",
    "Records can be any supported type in every project.": "В любом проекте можно хранить записи всех поддерживаемых типов.",
    "Sign in to access your family vault.": "Войдите, чтобы открыть семейное хранилище.",
    "Login": "Вход",
    "Good day,": "Здравствуйте,",
    "Sign in to access your family vault.": "Войдите, чтобы открыть семейное хранилище.",
    "This account is deactivated.": "Эта учетная запись отключена.",
    "Email or password is incorrect.": "Неверная электронная почта или пароль.",
    "Settings saved.": "Настройки сохранены.",
    "That email address is already used.": "Этот адрес электронной почты уже используется.",
    "Name and email are required.": "Необходимо указать имя и электронную почту.",
    "Share revoked.": "Общий доступ отозван.",
    "No project shares.": "Нет общих проектов.",
    "No record shares.": "Нет общих записей.",
    "No active members": "Нет активных участников",
    "Passwords": "Пароли",
    "Bank Cards": "Банковские карты",
    "Secrets": "Секреты",
    "Environment variable": "Переменная окружения",
    "Environment": "Среда",
    "Folders": "Папки",
    "records": "записей",
    "records across projects": "записей во всех проектах",
    "No records": "Нет записей",
    "Account activity": "Действия с учетной записью",
    "Shared by": "Поделился",
    "Updated": "Обновлено",
    "Copy": "Копировать",
    "Copy shared record": "Скопировать общую запись",
    "Copy to my vault": "Скопировать в мое хранилище",
    "Edit project": "Изменить проект",
    "Create a project": "Создать проект",
    "Edit folder": "Изменить папку",
    "Create a folder": "Создать папку",
    "Choose a new password": "Задайте новый пароль",
    "Change password": "Сменить пароль",
    "Your administrator assigned this password. Change it before continuing.": "Администратор назначил этот пароль. Смените его, чтобы продолжить.",
    "Use a strong password that you do not use elsewhere.": "Используйте надежный пароль, который вы больше нигде не применяете.",
    "The recipient will see future records added to this project.": "Получатель увидит новые записи, добавленные в этот проект.",
    "The recipient can view this record and optionally copy it into their vault.": "Получатель сможет просматривать запись и при желании скопировать ее в свое хранилище.",
    "Delete this folder and hide its records?": "Удалить папку и скрыть ее записи?",
    "Delete this record? Its history will remain available.": "Удалить запись? Ее история останется доступна.",
    "Delete this project and hide its records? Their history will be retained.": "Удалить проект и скрыть записи? История записей сохранится.",
    "Delete": "Удалить",
    "Activate": "Включить",
    "Deactivate": "Отключить",
    "New": "Новый",
    "Edit": "Изменить",
    "Good day,": "Здравствуйте,",
    "Account": "Учетная запись",
    "Shared read-only": "Общий доступ · только чтение",
    "Account security": "Безопасность учетной записи",
    "Email": "Электронная почта",
    "Username": "Имя пользователя",
    "Website": "Сайт",
    "Notes": "Заметки",
    "Title / key": "Название / ключ",
    "Cardholder": "Держатель карты",
    "Number": "Номер",
    "Expiration": "Срок действия",
    "Issuer": "Банк / эмитент",
    "Value": "Значение",
    "Variable key": "Ключ переменной",
    "Secret": "Секрет",
    "Plain": "Обычный текст",
    "The member will need to change this password at first sign-in.": "Участнику нужно будет сменить этот пароль при первом входе.",
    "Choose a preset…": "Выберите вариант…",
    "No projects available": "Нет доступных проектов",
    "No other active members": "Нет других активных участников",
    "A project with this name already exists.": "Проект с таким названием уже существует.",
    "Sign in": "Войти",
    "Dashboard": "Главная",
    "Add member": "Добавить участника",
    "Member accounts": "Учетные записи участников",
    "Shared with me": "Мне предоставлен доступ",
    "Settings": "Настройки",
    "Activity": "Активность",
    "Change password": "Сменить пароль",
    "Add a record": "Добавить запись",
    "Edit record": "Изменить запись",
    "New record": "Новая запись",
    "New project": "Новый проект",
    "New folder": "Новая папка",
    "Members": "Участники",
    "History": "История",
    "Reset password": "Сбросить пароль",
    "Delete member": "Удалить участника",
    "Share": "Поделиться",
    "Copy shared record": "Копирование общей записи",
    "Record type": "Тип записи",
    "This record uses the project type.": "Тип записи определяется типом проекта.",
    "Create a project before copying shared records.": "Сначала создайте проект, чтобы скопировать общую запись.",
    'Add a member': 'Добавить участника',
    'Live references shared by other members.': 'Общие ссылки на записи других участников.',
    'Records': 'Записи',
    'No other active members': 'Нет других активных участников',
    'Share with member': 'Поделиться с участником',
    'Current shares': 'Текущие ссылки общего доступа',
    'Vault record': 'Запись хранилища',
    'Sharing': 'Общий доступ',
    'Status': 'Статус',
    'Joined': 'Дата регистрации',
    'Actions': 'Действия',
    'New': 'Новая',
    'Edit': 'Изменить',
    'The recipient will see future records added to this project.': 'Получатель увидит новые записи, добавленные в этот проект.',
    'The recipient can view this record and optionally copy it into their vault.': 'Получатель сможет просматривать запись и при желании скопировать ее в свое хранилище.',
    'Name': 'Название',
    'Project type': 'Тип проекта',
    'Old password': 'Текущий пароль',
    'New password': 'Новый пароль',
    'New password confirmation': 'Подтверждение нового пароля',
    'Variable keys must use letters, numbers, and underscores, and cannot start with a number.': 'Ключи могут содержать латинские буквы, цифры и подчеркивания и не могут начинаться с цифры.',
    'An active project with this name already exists.': 'Проект с таким названием уже существует.',
    'An active folder with this name already exists in the project.': 'Папка с таким названием уже есть в проекте.',
    'An active folder with this name already exists.': 'Папка с таким названием уже существует.',
    'An active record with this name already exists in this location.': 'Запись с таким названием уже существует в этом месте.',
    'Environment variables can only be added to a Secrets project.': 'Переменные окружения можно добавлять только в проект «Секреты».',
    'Choose transfer or purge before permanently deleting the account.': 'Перед удалением выберите передачу или полное удаление данных.',
    'This account is deactivated.': 'Эта учетная запись отключена.',
    'Email or password is incorrect.': 'Неверная электронная почта или пароль.',
    'Settings saved.': 'Настройки сохранены.',
    'That email address is already used.': 'Этот адрес электронной почты уже используется.',
    'Name and email are required.': 'Необходимо указать имя и электронную почту.',
    'Share revoked.': 'Общий доступ отозван.',
    'Shared with': 'Предоставлен доступ:',
    'Copied into': 'Скопировано в проект «',
    'Could not import file:': 'Не удалось импортировать файл:',
    'Could not import': 'Не удалось импортировать',
    'Imported': 'Импортировано переменных:',
    'Choose an .env file smaller than 1 MB.': 'Выберите файл .env размером менее 1 МБ.',
    'Value type': 'Тип значения',
    'Card number': 'Номер карты',
    'Issuer / bank': 'Банк / эмитент',
    'Card PIN': 'PIN-код карты',
    'Environment / secret variable': 'Переменная окружения / секрет',
    'Read-only access': 'Доступ только для чтения',
    'Share': 'Поделиться',
    'No active shares.': 'Нет активных ссылок общего доступа.',
    'Password changed.': 'Пароль изменен.',
    'Member created': 'Участник создан',
    'Member deactivated': 'Участник отключен',
    'Member activated': 'Участник активирован',
    'Member password reset': 'Пароль участника сброшен',
    'Member deleted': 'Учетная запись участника удалена',
    'Project created': 'Проект создан',
    'Project updated': 'Проект изменен',
    'Project deleted': 'Проект удален',
    'Folder created': 'Папка создана',
    'Folder updated': 'Папка изменена',
    'Folder deleted': 'Папка удалена',
    'Record created': 'Запись создана',
    'Record updated': 'Запись изменена',
    'Record deleted': 'Запись удалена',
    'Record imported': 'Запись импортирована',
    'Record import updated': 'Импортированная запись обновлена',
    'Record copied': 'Запись скопирована',
    'Shared record viewed': 'Просмотрена общая запись',
    'Value reveal': 'Показано значение',
    'Value copy': 'Значение скопировано',
    'Project shared': 'Проект открыт для участника',
    'Record shared': 'Запись открыта для участника',
    'Env exported': 'Файл .env экспортирован',
    'Login': 'Вход',
    'Logout': 'Выход',
    'Password changed': 'Пароль изменен',
    'Good day': 'Здравствуйте',
    'Updated': 'Обновлено',
    'Account': 'Учетная запись',
    'by': 'участник:',
    'Former member': 'Бывший участник',
    'from': 'от',
    'No project shares.': 'Нет общих проектов.',
    'No record shares.': 'Нет общих записей.',
    'No active members': 'Нет активных участников',
    'You must select a valid choice.': 'Выберите один из предложенных вариантов.',
    'Select all': 'Выбрать все',
    'Select record': 'Выбрать запись',
    'Select member': 'Выберите участника',
    'Share selected': 'Поделиться выбранным',
    'Delete selected': 'Удалить выбранное',
    'Delete selected records? Their history will remain available.': 'Удалить выбранные записи? Их история останется доступна.',
    'Select at least one record.': 'Выберите хотя бы одну запись.',
    'Select a member.': 'Выберите участника.',
    'Environment file': 'Файл окружения',
    'Close': 'Закрыть',
    'Signed in': 'Вошел в систему',
    'Signed out': 'Вышел из системы',
    'Changed password': 'Изменил пароль',
    'Created member account': 'Создал учетную запись',
    'Deactivated member': 'Отключил участника',
    'Activated member': 'Включил участника',
    'Reset member password': 'Сбросил пароль участника',
    'Deleted member account': 'Удалил учетную запись',
    'Created project': 'Создал проект',
    'Updated project': 'Изменил проект',
    'Deleted project': 'Удалил проект',
    'Shared project': 'Открыл доступ к проекту',
    'Created folder': 'Создал папку',
    'Updated folder': 'Изменил папку',
    'Deleted folder': 'Удалил папку',
    'Created record': 'Создал запись',
    'Updated record': 'Изменил запись',
    'Deleted record': 'Удалил запись',
    'Imported record': 'Импортировал запись',
    'Updated imported record': 'Обновил импортированную запись',
    'Copied record': 'Скопировал запись',
    'Shared record': 'Открыл доступ к записи',
    'Viewed shared record': 'Просмотрел общую запись',
    'Revealed value': 'Показал значение',
    'Copied value': 'Скопировал значение',
    'Exported environment file': 'Экспортировал файл окружения',
    'By': 'Выполнил',
    'Project contents': 'Содержимое проекта',
    'Project records': 'Записи проекта',
    'Open folder': 'Открыть папку',
    'Shared project': 'Общий проект',
    'Shared records': 'Общие записи',
    'No shared contents.': 'Нет общих записей или папок.',
    'No shared items yet.': 'Пока нет общих элементов.',
    'Icon': 'Значок',
    'Key': 'Ключ',
    'Credit card': 'Банковская карта',
    'Code': 'Код',
    'Lock': 'Замок',
    'Grid': 'Сетка',
    'Shield': 'Щит',
    'Server': 'Сервер',
    'Database': 'База данных',
    'Globe': 'Глобус',
    'Briefcase': 'Портфель',
    'Star': 'Звезда',
    'Home': 'Дом',
    'Cloud': 'Облако',
    'Bolt': 'Молния',
    "Breadcrumb": "Навигационная цепочка",
    "Delete {name}?": "Удалить {name}?",
    "For {name}": "Для {name}",
    "Temporary password set. The member must change it at next sign-in.": "Временный пароль установлен. Участник должен сменить его при следующем входе.",
    "Account permanently deleted.": "Учётная запись окончательно удалена.",
    "Too many failed sign-in attempts. Try again in a few minutes.": "Слишком много неудачных попыток входа. Повторите через несколько минут.",
    "This record type is not available in this project.": "Этот тип записи недоступен в данном проекте.",
    "Choose a .env file smaller than 1 MB.": "Выберите файл .env размером меньше 1 МБ.",
    "Created account for {name}. They must change the assigned password at first login.": "Создана учётная запись для {name}. При первом входе нужно сменить назначенный пароль.",
    "{name} is active.": "{name}: учётная запись активна.",
    "{name} is deactivated.": "{name}: учётная запись деактивирована.",
    "Deleted {count} record(s).": "Удалено записей: {count}.",
    "Shared {count} record(s) with {name}.": "Записей предоставлено: {count}, получатель: {name}.",
    "Shared with {name}.": "Доступ предоставлен: {name}.",
    "Copied into {name}.": "Скопировано в {name}.",
    "Imported {count} variables.": "Импортировано переменных: {count}.",
    "Could not import file: {detail}": "Не удалось импортировать файл: {detail}",
    "Could not import {key}: a non-variable record already uses that name.": "Не удалось импортировать {key}: имя уже занято записью другого типа.",
    "An account with this email already exists.": "Учётная запись с таким адресом электронной почты уже существует.",
    "Record type cannot be changed.": "Тип записи изменить нельзя.",
    "Invalid JSON: {detail}": "Некорректный JSON: {detail}",
    "File storage is not configured on this server.": "Хранилище файлов на этом сервере не настроено.",
    "Could not store the image. Try again later.": "Не удалось сохранить изображение. Повторите попытку позже.",
    "Could not store the file. Try again later.": "Не удалось сохранить файл. Повторите попытку позже.",
    "Could not copy the file. Try again later.": "Не удалось скопировать файл. Повторите попытку позже.",
    "Users": "Пользователи",
    "Clock": "Часы",
    "Line {n}: expected KEY=value": "Строка {n}: ожидается KEY=value",
    "Line {n}: invalid variable name": "Строка {n}: недопустимое имя переменной",
    "Close menu": "Закрыть меню", "Open record": "Открыть запись", "Open menu": "Открыть меню", "Menu": "Меню",
}

_PLACEHOLDER = re.compile(r"\{(\w+)\}")
_patterns = {}


def _table_patterns(language, table):
    """Entries with ``{name}`` placeholders, compiled once, so messages built with f-strings still translate."""
    if language not in _patterns:
        compiled = []
        for key, value in table.items():
            if "{" in key:
                regex = "".join(f"(?P<{part}>.+?)" if i % 2 else re.escape(part) for i, part in enumerate(_PLACEHOLDER.split(key)))
                compiled.append((re.compile(f"^{regex}$", re.S), value))
        _patterns[language] = compiled
    return _patterns[language]


def translate(language, value, **params):
    """English text -> text in ``language``; falls back to English when there is no entry.

    Keys may contain ``{name}`` placeholders: filled from ``params`` or, for an already formatted message
    (``Deleted 3 record(s).``), from the text matched against the key.
    """
    text = str(value)
    table = RU if language == "ru" else TABLES.get(language)
    if table:
        translated = table.get(text)
        if translated is None:
            for regex, candidate in _table_patterns(language, table):
                match = regex.match(text)
                if match:
                    translated, params = candidate, {**match.groupdict(), **params}
                    if "detail" in params:  # nested message, e.g. the parser error inside "Could not import file: …"
                        params["detail"] = translate(language, params["detail"])
                    break
        if translated is None:
            # Audit action identifiers and display strings can be generated dynamically.
            translated = table.get(text.replace("_", " ").title())
        if translated is not None:
            text = translated
    return text.format(**params) if params else text


@register.simple_tag(takes_context=True)
def tr(context, value, **params):
    request = context.get("request")
    return translate(getattr(getattr(request, "user", None), "preferred_language", "en"), value, **params)


@register.simple_tag(takes_context=True)
def activity_label(context, action):
    label = ACTIVITY_LABELS.get(str(action), str(action).replace("_", " ").capitalize())
    return tr(context, label)
