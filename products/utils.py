def is_list_in_another(small, big):
	return all(item in big for item in small)
