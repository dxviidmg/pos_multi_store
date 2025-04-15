def is_list_in_another(small, big):
	return all(item in big for item in small)


def is_positive_number(value):
    try:
        return value is not None and float(value) > 0
    except (ValueError, TypeError):
        return False