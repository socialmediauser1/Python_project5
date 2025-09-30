class TemplateEngine:
    def render(self, template: str, context: dict) -> str:
        try:
            file = open(template, 'r', encoding='utf-8')
            try:
                template = file.read()
            finally:
                file.close()
        except Exception:
            pass
        previous = None
        while previous != template:
            previous = template
            template = self.render_for_once(template, context)
            template = self.render_if_once(template, context)
        return self.render_vars(template, context)

    def render_vars(self, text: str, context: dict) -> str:
        index, out, length = 0, [], len(text)
        while index < length:
            open_pos = text.find("{{", index)
            if open_pos == -1:
                out.append(text[index:]); break
            out.append(text[index:open_pos])
            close_pos = text.find("}}", open_pos + 2)
            if close_pos == -1:
                out.append(text[open_pos:]); break
            key = text[open_pos + 2:close_pos].strip()
            out.append("" if key == "" else str(context.get(key, "")))
            index = close_pos + 2
        return "".join(out)

    def render_if_once(self, text: str, context: dict) -> str:
        start = text.find("{% if ")
        if start == -1:
            return text
        head_end = text.find("%}", start)
        if head_end == -1:
            return text
        index, depth, block_end = head_end + 2, 1, -1
        elif_positions, else_position = [], -1
        while index < len(text):
            next_if = text.find("{% if ", index)
            next_elif = text.find("{% elif", index)
            next_else = text.find("{% else %}", index)
            next_end = text.find("{% endif %}", index)
            candidates = [position for position in [next_if, next_elif, next_else, next_end] if position != -1]
            if not candidates:
                break
            next_index = min(candidates)
            if next_index == next_if:
                depth += 1
                index = text.find("%}", next_index) + 2
            elif next_index == next_end:
                depth -= 1
                if depth == 0:
                    block_end = next_index
                    break
                index = next_index + len("{% endif %}")
            elif depth == 1 and next_index == next_else:
                else_position = next_index
                index = next_index + len("{% else %}")
            elif depth == 1 and next_index == next_elif:
                elif_positions.append(next_index)
                index = text.find("%}", next_index) + 2
            else:
                index = text.find("%}", next_index) + 2

        if block_end == -1:
            return text

        condition = text[start + len("{% if "):head_end].strip()
        headers = [("if", condition, start, head_end+2)]
        for position in elif_positions:
            tag_end = text.find("%}", position)
            headers.append(("elif", text[position + len("{% elif"):tag_end].strip(), position, tag_end + 2))
        if else_position != -1:
            headers.append(("else", None, else_position, else_position+len("{% else %}")))

        branches = []
        for index, header in enumerate(headers):
            _, condition_str, _, header_end = header
            next_start = headers[index+1][2] if index + 1 < len(headers) else block_end
            content = text[header_end:next_start]
            branches.append((condition_str, content))

        chosen_content = ""
        picked = False
        for condition_str, content in branches:
            if condition_str is None:
                if not picked: chosen_content = content
                break
            if self.evaluate(condition_str, context):
                chosen_content = content
                picked = True
                break

        inner = self.render_for_once(chosen_content, context)
        inner = self.render_if_once(inner, context)

        after = text.find("{% endif %}", block_end) + len("{% endif %}")
        return text[:start] + inner + text[after:]

    def evaluate(self, expression: str, context: dict) -> bool:
        expression = expression.strip()
        operators = ["==", "!=", ">=", "<=", ">", "<"]
        for operator in operators:
            position = expression.find(operator)
            if position != -1:
                left = expression[:position].strip()
                right = expression[position + len(operator):].strip()
                left_value = context.get(left, None)
                right_value = self.to_num(right, context)
                try:
                    if operator == "==": return left_value == right_value
                    if operator == "!=": return left_value != right_value
                    if operator == ">=": return left_value >= right_value
                    if operator == "<=": return left_value <= right_value
                    if operator == ">":  return left_value >  right_value
                    if operator == "<":  return left_value <  right_value
                except Exception:
                    return False
        return bool(context.get(expression, None))

    def to_num(self, text: str, context: dict):
        if text and (text.isdigit() or (text[0] == "-" and text[1:].isdigit())):
            try: return int(text)
            except Exception: pass
        if len(text) >= 2 and text[0] == text[-1] and text[0] in ("'", '"'):
            return text[1:-1]
        return context.get(text, "")

    def render_for_once(self, text: str, context: dict) -> str:
        start = text.find("{% for ")
        if start == -1:
            return text
        head_end = text.find("%}", start)
        if head_end == -1:
            return text
        index, depth, block_end = head_end + 2, 1, -1
        while index < len(text):
            next_for = text.find("{% for ", index)
            next_end = text.find("{% endfor %}", index)
            if next_end == -1 and next_for == -1:
                break
            next_index = min(position for position in [next_for, next_end] if position != -1)
            if next_index == next_for:
                depth += 1
                index = text.find("%}", next_index) + 2
            else:
                depth -= 1
                if depth == 0:
                    block_end = next_index
                    break
                index = next_index + len("{% endfor %}")
        if block_end == -1:
            return text

        header = text[start + len("{% for "):head_end].strip()
        parts = [part for part in header.split() if part]
        var_name, list_name = (parts[0], parts[2]) if len(parts) >= 3 and parts[1] == "in" else ("item", "items")
        inner = text[head_end + 2:block_end]

        sequence = context.get(list_name, []) or []
        rendered = []
        sentinel = object()
        old_value = context.get(var_name, sentinel)
        for value in sequence:
            context[var_name] = value
            piece = self.render_for_once(inner, context)
            piece = self.render_if_once(piece, context)
            piece = self.render_vars(piece, context)
            rendered.append(piece)
        if old_value is sentinel:
            if var_name in context: del context[var_name]
        else:
            context[var_name] = old_value

        after = text.find("{% endfor %}", block_end) + len("{% endfor %}")
        return text[:start] + "".join(rendered) + text[after:]