from .managers import TenantManager, StoreManager, ProductManager
import xlrd
import tqdm


def read_excel_file(file_path):
    workbook = xlrd.open_workbook(file_path)
    return workbook.sheet_by_index(0)

def run():
    file_path = "scripts/data/suga/SmartVenta_plantilla_importacion_productos (11).xls"
    file = read_excel_file(file_path)
    
    max_length = 0
    sum_lengths = 0
    for row_idx in range(1, file.nrows):
#        print(row_idx)
        row_values = file.row_values(row_idx)
        current_length = len(row_values[3])

        if current_length > max_length:
            max_length = current_length
            print(row_idx, max_length)

        if current_length > 100:
            sum_lengths += 1

    print(sum_lengths * file.nrows / 100, '%')
