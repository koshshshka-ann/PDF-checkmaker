#!/usr/bin/env python3
"""
PDF Генератор с CLI-интерфейсом
Без зависимости от weasyprint.fonts — работает при базовой установке
"""

import os
import sys
import json
import csv
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any
import logging
from html import escape
from weasyprint import HTML, CSS
import inquirer
from rich.console import Console
from rich.table import Table
from rich.progress import track
from rich.prompt import IntPrompt, Confirm

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("pdf_generator.log", encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

console = Console()

# Пути
ROOT_DIR = Path(__file__).parent.absolute()
DATA_DIR = ROOT_DIR / "data"
TEMPLATES_DIR = ROOT_DIR / "templates"
OUTPUT_DIR = ROOT_DIR / "output"


# Создание папок
def create_directories():
    for directory in [DATA_DIR, TEMPLATES_DIR, OUTPUT_DIR]:
        directory.mkdir(exist_ok=True)
        logger.info(f"Папка {'создана' if not directory.exists() else 'уже существует'}: {directory}")


# Поиск данных
def find_data_files() -> List[Path]:
    files = []
    for pattern in ["*.csv", "*.json"]:
        files.extend(DATA_DIR.rglob(pattern))
    return sorted(files)


def find_template_files() -> List[Path]:
    return sorted(TEMPLATES_DIR.rglob("*.html"))


# Чтение данных
def load_csv(file_path: Path) -> List[Dict[str, Any]]:
    try:
        df = pd.read_csv(file_path)
        for col in df.columns:
            if df[col].dtype == 'object':
                try:
                    df[col] = pd.to_datetime(df[col], errors='ignore')
                except:
                    pass
        return df.to_dict('records')
    except Exception as e:
        logger.error(f"Ошибка чтения CSV {file_path}: {e}")
        return []


def load_json(file_path: Path) -> List[Dict[str, Any]]:
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return [data] if isinstance(data, dict) else data
    except Exception as e:
        logger.error(f"Ошибка чтения JSON {file_path}: {e}")
        return []


def load_data(file_path: Path) -> List[Dict[str, Any]]:
    if file_path.suffix.lower() == '.csv':
        return load_csv(file_path)
    elif file_path.suffix.lower() == '.json':
        return load_json(file_path)
    else:
        logger.warning(f"Неподдерживаемый формат: {file_path}")
        return []


# Проверка HTML
def validate_html(content: str) -> bool:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(content, "html.parser")
    return soup.find() is not None


# Поиск плейсхолдеров
def extract_placeholders(template_content: str) -> List[str]:
    import re
    placeholders = re.findall(r'\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}', template_content)
    return list(set(placeholders))


# Рендер шаблона
def render_template(template_content: str, data: Dict[str, Any]) -> str:
    result = template_content
    for key, value in data.items():
        if isinstance(value, (pd.Timestamp, datetime)):
            value = value.strftime('%d.%m.%Y %H:%M:%S')
        else:
            value = str(value)
        result = result.replace(f"{{{{ {key} }}}}", escape(value))
    return result


# Генерация PDF без FontConfiguration
def generate_pdf(html_content: str, output_path: Path):
    try:
        css = '''
        @page { size: A4; margin: 1.5cm; }
        body { 
            font-family: 'DejaVu Sans', 'Arial', sans-serif; 
            font-size: 11pt;
        }
        table { width: 100%; border-collapse: collapse; margin: 1em 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .header { font-size: 1.5em; font-weight: bold; margin-bottom: 1em; color: #333; }
        .footer { font-size: 0.8em; color: #666; margin-top: 2em; text-align: center; }
        '''
        HTML(string=html_content, base_url=str(TEMPLATES_DIR)).write_pdf(
            target=str(output_path),
            stylesheets=[CSS(string=css)]
        )
        logger.info(f"PDF сохранён: {output_path}")
    except Exception as e:
        logger.error(f"Ошибка генерации PDF: {e}")
        raise


# Автооткрытие файла
def open_pdf(file_path: Path):
    try:
        if sys.platform.startswith('darwin'):
            subprocess.call(['open', file_path])
        elif sys.platform.startswith('linux'):
            subprocess.call(['xdg-open', file_path])
        elif sys.platform.startswith('win'):
            os.startfile(file_path)
    except Exception as e:
        logger.warning(f"Не удалось открыть PDF: {e}")


# Печать таблицы данных
def display_data_preview(data_list: List[Dict], title: str = "Предпросмотр данных"):
    if not data_list:
        console.print("[yellow]Нет данных для отображения.[/yellow]")
        return
    table = Table(title=title)
    headers = data_list[0].keys()
    for header in headers:
        table.add_column(header, overflow="fold")
    for item in data_list[:10]:
        table.add_row(*[str(item.get(h, "")) for h in headers])
    console.print(table)
    if len(data_list) > 10:
        console.print(f"[dim]и ещё {len(data_list) - 10} записей...[/dim]")


# Основной интерфейс
def main():
    console.print("[bold blue]=== PDF ГЕНЕРАТОР ===[/bold blue]")

    create_directories()

    data_files = find_data_files()
    template_files = find_template_files()

    if not data_files:
        console.print("[red]Не найдено файлов данных в папке /data.[/red]")
        return
    if not template_files:
        console.print("[red]Не найдено шаблонов в папке /templates.[/red]")
        return

    # Выбор файла данных
    console.print("\n[bold]Доступные файлы данных:[/bold]")
    for i, file in enumerate(data_files, 1):
        console.print(f"[{i}] {file.name}")

    data_choice = IntPrompt.ask("Выберите файл", choices=[str(i) for i in range(1, len(data_files) + 1)])
    selected_data_file = data_files[data_choice - 1]

    # Загрузка
    console.print(f"[green]Загрузка данных из {selected_data_file.name}...[/green]")
    data_records = load_data(selected_data_file)
    if not data_records:
        console.print("[red]Не удалось загрузить данные.[/red]")
        return
    console.print(f"[green]Загружено {len(data_records)} записей.[/green]")

    # Предпросмотр
    display_data_preview(data_records[:5], "Первые 5 записей")

    # Выбор шаблона
    console.print("\n[bold]Доступные шаблоны:[/bold]")
    for i, file in enumerate(template_files, 1):
        console.print(f"[{i}] {file.name}")

    template_choice = IntPrompt.ask("Выберите шаблон", choices=[str(i) for i in range(1, len(template_files) + 1)])
    selected_template_file = template_files[template_choice - 1]

    # === ОБЪЯВЛЕНИЕ ПЕРЕМЕННЫХ ДО ИСПОЛЬЗОВАНИЯ ===
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Чтение шаблона (один раз!)
    try:
        with open(selected_template_file, 'r', encoding='utf-8') as f:
            template_content = f.read()
    except Exception as e:
        console.print(f"[red]Ошибка чтения шаблона: {e}[/red]")
        return

    if not validate_html(template_content):
        console.print("[red]Некорректный HTML в шаблоне.[/red]")
        return

    placeholders = extract_placeholders(template_content)
    console.print(f"[blue]Требуемые поля: {', '.join(placeholders) or 'не найдены'}[/blue]")

    # === РЕЖИМ: СВОДНЫЙ СЧЁТ ===
    if "order_invoice" in selected_template_file.name.lower():
        console.print("\n[bold yellow]Генерация сводного счёта...[/bold yellow]")

        selected_products = data_records[:3]
        if len(selected_products) == 0:
            console.print("[red]Недостаточно данных для формирования счёта.[/red]")
            return

        table_rows = ""
        grand_total = 0
        for i, prod in enumerate(selected_products, 1):
            name = escape(str(prod.get('name', 'Неизвестно')))
            category = escape(str(prod.get('category', 'Разное')))
            price = int(prod.get('price', 0))
            quantity = 1
            total = price * quantity
            grand_total += total

            table_rows += f"""
            <tr>
                <td>{i}</td>
                <td>{name}</td>
                <td>{category}</td>
                <td>{price}</td>
                <td>{quantity}</td>
                <td>{total}</td>
            </tr>
            """

        invoice_data = {
            "invoice_id": "INV-1001",
            "customer_name": "ИП Петров",
            "date": datetime.now().strftime("%d.%m.%Y"),
            "payment_method": "Безнал",
            "table_rows": table_rows,
            "grand_total": grand_total
        }

        html_content = template_content
        for key, value in invoice_data.items():
            html_content = html_content.replace(f"{{{{ {key} }}}}", str(value))

        output_path = OUTPUT_DIR / f"order_invoice_{invoice_data['invoice_id']}_{timestamp}.pdf"
        generated_files = []  # временный список

        try:
            generate_pdf(html_content, output_path)
            console.print(f"[green]✅ Счёт сохранён: {output_path.name}[/green]")
            generated_files.append(output_path)
        except Exception as e:
            console.print(f"[red]❌ Ошибка генерации: {e}[/red]")
            return

        if Confirm.ask("Открыть счёт?", default=True):
            open_pdf(output_path)

        console.print(f"[bold green]Готово! Счёт на {grand_total} ₽ сгенерирован.[/bold green]")
        return  # завершаем

    # === ОБЫЧНЫЙ РЕЖИМ: ПО КАРТОЧКАМ ===
    batch_mode = Confirm.ask("Сгенерировать все записи?", default=False)
    generated_files = []
    id_field = 'id' if 'id' in data_records[0] else next(iter(data_records[0].keys()))

    if batch_mode:
        for record in track(data_records, description="Генерация PDF..."):
            try:
                html_content = render_template(template_content, record)
                safe_id = str(record.get(id_field, 'unknown')).replace(' ', '_')
                output_path = OUTPUT_DIR / f"{selected_template_file.stem}_{safe_id}_{timestamp}.pdf"
                generate_pdf(html_content, output_path)
                generated_files.append(output_path)
            except Exception as e:
                logger.error(f"Ошибка при записи {record}: {e}")
    else:
        console.print("\n[bold]Выберите запись:[/bold]")
        for i, record in enumerate(data_records):
            console.print(f"[{i+1}] {record.get(id_field, 'без ID')}")
        record_choice = IntPrompt.ask("Номер", choices=[str(i) for i in range(1, len(data_records) + 1)])
        selected_record = data_records[record_choice - 1]

        try:
            html_content = render_template(template_content, selected_record)
            safe_id = str(selected_record.get(id_field, 'unknown')).replace(' ', '_')
            output_path = OUTPUT_DIR / f"{selected_template_file.stem}_{safe_id}_{timestamp}.pdf"
            generate_pdf(html_content, output_path)
            generated_files.append(output_path)
            console.print(f"[green]PDF создан: {output_path.name}[/green]")
        except Exception as e:
            console.print(f"[red]Ошибка генерации: {e}[/red]")
            return

    # Открытие последнего PDF
    if generated_files and Confirm.ask("Открыть PDF?", default=True):
        open_pdf(generated_files[-1])

    console.print(f"[bold green]Готово! Сгенерировано {len(generated_files)} PDF.[/bold green]")


if __name__ == "__main__":
    try:
        import subprocess
        main()
    except KeyboardInterrupt:
        console.print("\n[red]Прервано.[/red]")
    except Exception as e:
        logger.critical(f"Ошибка: {e}")
        console.print(f"[red]Ошибка: {e}[/red]")
