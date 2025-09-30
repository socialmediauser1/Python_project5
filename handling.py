from TemplateEngine import TemplateEngine

template = TemplateEngine()

def _html(text):
    return text

def handle_hello_person(name, age, city):
    context = {"name": name, "age": age, "city": city, "nickname": "Guest"}
    html = template.render("templates/greeting.html", context)
    return _html(html)

def handle_profile(name, age):
    context = {"name": name, "age": age}
    html = template.render("templates/profile.html", context)
    return _html(html)

def handle_status(temperature):
    context = {"temperature": temperature}
    html = template.render("templates/status.html", context)
    return _html(html)

def handle_tasks():
    context = {"tasks": ["Write report", "Gym", "Call mom", "Read 10 pages"]}
    html = template.render("templates/tasks.html", context)
    return _html(html)
