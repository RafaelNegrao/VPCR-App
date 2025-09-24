import flet as ft
import json
import os
import sqlite3
from datetime import datetime
import asyncio
import threading
from typing import List, Dict, Tuple

try:
    import openpyxl  # Para leitura de planilhas Excel (xlsx, xlsm)
except ImportError:
    openpyxl = None  # Lidaremos com ausência mostrando mensagem ao usuário

class FileImportManager:
    """Gerencia importação e validação de arquivos Excel para VPCR."""

    # Header completo esperado conforme especificação do usuário
    EXPECTED_HEADER_ORDER = [
        "VPCR Project ID",
        "Initiated Date",
        "VPCR Title",
        "Sourcing Manager",
        "SQIE(s)",
        "Supporting Documentation",
        "Project Editor",
        "Change Manager",
        "Affected Items",
        "Plants Affected - Post CPIF Integration",
        "Desired Production Date at Affected Plant(s)",
        "SCR Item ID",
        "VPCR Status",
        "Type of VPCR",
        "Current Supplier",
        "Proposed Supplier",
        "Category 3 (Group)",
        "Category 2 (Area)",
        "VPCR Requestor",
        "Last Updated Date"
    ]

    def __init__(self, app_ref: 'VPCRApp'):
        self.app = app_ref
        self.validated_files: List[Dict] = []  # {path, header_ok, errors, header}
        self.file_picker = None  # Será criado quando a página existir
        self.files_list_container: ft.Container | None = None
        self.import_dialog = None
        self.header_model_dialog = None

    # ================= Public API =================
    def build_file_picker(self):
        """Cria (se ainda não criado) o FilePicker do Flet e registra callbacks."""
        if self.file_picker is not None:
            return self.file_picker

        def on_result(e: ft.FilePickerResultEvent):
            if not e.files:
                return
            paths = [f.path for f in e.files]
            self.validate_files(paths)
            self._update_files_listing()

        self.file_picker = ft.FilePicker(on_result=on_result)
        self.app.page.overlay.append(self.file_picker)
        return self.file_picker

    def open_file_dialog(self):
        """Abre janela do sistema para seleção de arquivos Excel."""
        if self.file_picker is None:
            self.build_file_picker()
        # Filtros de extensão (xlsx, xlsm, xlsb - xlsb não suportado por openpyxl mas permitimos seleção)
        self.file_picker.pick_files(allow_multiple=True, allowed_extensions=['xlsx','xlsm','xlsb'])

    def open_import_window(self):
        """Abre janela principal de importação (parecida com a de TODO)."""
        colors = self.app.theme_manager.get_theme_colors()

        def close_window(e=None):
            try:
                self.app.page.close(self.import_dialog)
            except Exception:
                if self.app.page.dialog:
                    self.app.page.dialog.open = False
                    self.app.page.update()

        def select_files(e):
            self.open_file_dialog()

        def open_header_model(e):
            self.open_header_model_dialog()

        # Área onde os arquivos aparecerão
        self.files_list_container = ft.Container(
            content=ft.Column([], spacing=10, scroll=ft.ScrollMode.AUTO),
            height=240,
            bgcolor=colors['secondary'],
            padding=10,
            border_radius=10
        )

        body = ft.Container(
            bgcolor=colors['secondary'],
            padding=15,
            border_radius=12,
            content=ft.Column([
            ft.Text("Importar Arquivos VPCR", size=16, weight=ft.FontWeight.BOLD),
            ft.Text("Selecione arquivos Excel (.xlsx/.xlsm). Cada arquivo será validado.", size=12, color=colors['text_container_secondary']),
            ft.Row([
                ft.ElevatedButton("Selecionar Arquivos", icon=ft.Icons.FILE_OPEN, on_click=select_files),
                ft.TextButton("Ver modelo do header", on_click=open_header_model)
            ], spacing=10),
            ft.Divider(),
            ft.Text("Arquivos selecionados:", size=12, weight=ft.FontWeight.BOLD),
            self.files_list_container,
            ft.Text(
                "Regras: A1='VPCR Project ID' e coluna T='Last Updated Date'. Cabeçalho completo deve seguir o modelo.",
                size=11,
                color=ft.Colors.ORANGE_300
            )
        ], spacing=12, width=760, height=500)
        )

        self.import_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Importar VPCR", size=18, weight=ft.FontWeight.BOLD, color=colors['text_container_primary']),
            content=body,
            bgcolor=colors['secondary'],
            actions=[
                ft.TextButton("Fechar", on_click=close_window),
                ft.ElevatedButton("Importar", icon=ft.Icons.UPLOAD, on_click=lambda e: self.execute_import())
            ],
            actions_alignment=ft.MainAxisAlignment.END
        )
        self.app.page.open(self.import_dialog)
        # Atualizar listagem se já existir conteúdo
        self._update_files_listing()

    def open_header_model_dialog(self):
        """Exibe diálogo com duas colunas: Campo | Letra da Coluna."""
        colors = self.app.theme_manager.get_theme_colors()

        def idx_to_col_letter(idx: int) -> str:
            # idx 1-based
            letters = ""
            while idx > 0:
                idx, rem = divmod(idx - 1, 26)
                letters = chr(65 + rem) + letters
            return letters

        # DataTable para visualização mais clara
        rows = []
        for i, field in enumerate(self.EXPECTED_HEADER_ORDER, start=1):
            letter = idx_to_col_letter(i)
            rows.append(ft.DataRow(cells=[
                ft.DataCell(ft.Text(field, size=12, color=colors['text_container_primary'])),
                ft.DataCell(ft.Text(letter, size=12, weight=ft.FontWeight.BOLD, color=colors['accent']))
            ]))

        data_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Campo", size=12, weight=ft.FontWeight.BOLD, color=colors['text_container_primary'])),
                ft.DataColumn(ft.Text("Coluna", size=12, weight=ft.FontWeight.BOLD, color=colors['text_container_primary']))
            ],
            rows=rows,
            heading_row_color=ft.Colors.with_opacity(0.2, colors['accent']),
            data_row_color={"hovered": colors['surface']}
        )

        grid = ft.Container(
            content=ft.Column([
                ft.Container(
                    content=data_table,
                    expand=True
                )
            ], expand=True, scroll=ft.ScrollMode.AUTO),
            height=420,
            bgcolor=colors['secondary'],
            padding=10,
            border_radius=10
        )

        def close_header(e=None):
            try:
                self.app.page.close(self.header_model_dialog)
            except Exception:
                if self.app.page.dialog:
                    self.app.page.dialog.open = False
                    self.app.page.update()

        self.header_model_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text("Modelo de Header", size=18, weight=ft.FontWeight.BOLD, color=colors['text_container_primary']),
            content=grid,
            bgcolor=colors['secondary'],
            actions=[ft.TextButton("Fechar", on_click=close_header)],
            actions_alignment=ft.MainAxisAlignment.END
        )
        self.app.page.open(self.header_model_dialog)

    # (Antigo show_import_review_dialog removido; listagem agora na janela principal)

    # ================= Internal Helpers =================
    def validate_files(self, paths: List[str]):
        """Valida lista de arquivos de forma síncrona adicionando aos existentes.
        Evita duplicar caminhos já validados anteriormente."""
        existing_paths = {f['path'] for f in self.validated_files}
        for path in paths:
            if path not in existing_paths:
                self.validated_files.append(self._validate_file(path))

    def _validate_file(self, path: str) -> Dict:
        header_ok = False
        errors: List[str] = []
        header_values: List[str] = []
        # Ler arquivo
        if openpyxl is None and path.lower().endswith(('.xlsx', '.xlsm')):
            errors.append("Dependência 'openpyxl' não instalada")
        else:
            if path.lower().endswith('.xlsb'):
                errors.append("Formato .xlsb não suportado (use .xlsx ou .xlsm)")
            else:
                try:
                    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
                    ws = wb.active
                    for idx in range(1, len(self.EXPECTED_HEADER_ORDER) + 1):
                        cell_value = ws.cell(row=1, column=idx).value
                        header_values.append(str(cell_value).strip() if cell_value is not None else "")
                    wb.close()
                except Exception as ex:
                    errors.append(f"Erro leitura: {ex}")

        if header_values:
            if header_values[0] != 'VPCR Project ID':
                errors.append("A1 != 'VPCR Project ID'")
            if len(header_values) >= 20 and header_values[19] != 'Last Updated Date':
                errors.append("Coluna T != 'Last Updated Date'")
            if header_values[:len(self.EXPECTED_HEADER_ORDER)] != self.EXPECTED_HEADER_ORDER:
                errors.append("Ordem diferente do modelo")
            if not errors:
                header_ok = True
        return {
            'path': path,
            'header_ok': header_ok,
            'errors': errors,
            'header': header_values
        }

    def _update_files_listing(self):
        if not self.files_list_container:
            return
        colors = self.app.theme_manager.get_theme_colors()
        col: ft.Column = self.files_list_container.content  # type: ignore
        col.controls.clear()
        if not self.validated_files:
            col.controls.append(ft.Text("Nenhum arquivo selecionado", size=12, color=colors['text_container_secondary']))
        else:
            for info in self.validated_files:
                status_color = ft.Colors.GREEN if info['header_ok'] else ft.Colors.RED
                errors_text = "; ".join(info['errors']) if info['errors'] else "OK"

                def make_remove(path):
                    return lambda e: self.remove_file(path)

                card = ft.Card(
                    color=colors['card_bg'] if 'card_bg' in colors else colors['surface'],
                    elevation=2,
                    content=ft.Container(
                        padding=12,
                        content=ft.Column([
                            ft.Row([
                                ft.Icon(ft.Icons.CHECK_CIRCLE if info['header_ok'] else ft.Icons.ERROR, color=status_color, size=22),
                                ft.Text(os.path.basename(info['path']), size=13, weight=ft.FontWeight.BOLD, color=colors['text_container_primary'], expand=True),
                                ft.IconButton(icon=ft.Icons.DELETE, icon_color=ft.Colors.RED_400, tooltip="Remover arquivo", on_click=make_remove(info['path']))
                            ], spacing=8),
                            ft.Text(errors_text, size=11, color=colors['text_container_secondary'])
                        ], spacing=6)
                    )
                )
                col.controls.append(card)
        self.files_list_container.update()

    def remove_file(self, path: str):
        self.validated_files = [f for f in self.validated_files if f['path'] != path]
        self._update_files_listing()
        # feedback
        try:
            self.app.page.snack_bar = ft.SnackBar(content=ft.Text(f"Arquivo removido: {os.path.basename(path)}"), duration=1500)
            self.app.page.snack_bar.open = True
            self.app.page.update()
        except Exception:
            pass

    def execute_import(self):
        """Executa a importação dos arquivos selecionados"""
        if not self.validated_files:
            self.app.show_custom_notification(
                "Nenhum arquivo selecionado para importação.", 
                color=ft.Colors.ORANGE_400
            )
            return
        
        try:
            total_imported = 0
            total_updated = 0
            total_lines = 0
            errors = []
            
            # Mostrar notificação de início
            self.app.show_custom_notification(
                f"Iniciando importação de {len(self.validated_files)} arquivo(s)...", 
                color=ft.Colors.BLUE_400
            )
            
            for file_info in self.validated_files:
                file_path = file_info['path']
                file_name = os.path.basename(file_path)
                
                try:
                    # Contar linhas do arquivo antes da importação
                    import pandas as pd
                    df = pd.read_excel(file_path)
                    lines_in_file = len(df)
                    total_lines += lines_in_file
                    
                    print(f"Processando {file_name}: {lines_in_file} linhas encontradas")
                    
                    # Executar importação via DatabaseManager
                    result = self.app.db_manager.import_from_excel(file_path)
                    
                    if result['success']:
                        total_imported += result['imported']
                        total_updated += result['updated']
                        print(f"✓ {file_name}: {result['imported']} novos, {result['updated']} atualizados")
                    else:
                        errors.append(f"{file_name}: {result.get('error', 'Erro desconhecido')}")
                        print(f"✗ {file_name}: {result.get('error', 'Erro desconhecido')}")
                        
                except Exception as e:
                    error_msg = f"{file_name}: {str(e)}"
                    errors.append(error_msg)
                    print(f"✗ {error_msg}")
            
            # Mostrar resultado final
            if total_imported > 0 or total_updated > 0:
                success_message = (
                    f"🎉 Importação concluída!\n"
                    f"📊 Total de linhas processadas: {total_lines}\n"
                    f"✅ Novos itens: {total_imported}\n"
                    f"🔄 Itens atualizados: {total_updated}\n"
                    f"📁 Arquivos processados: {len(self.validated_files)}"
                )
                
                if errors:
                    success_message += f"\n⚠️ Erros: {len(errors)}"
                
                # Atualizar dados na aplicação principal
                self.app.refresh_data_from_db()
                
                # Usar notificação de sucesso ou warning se houver erros
                color = ft.Colors.GREEN_400 if not errors else ft.Colors.ORANGE_400
                self.app.show_custom_notification(success_message, color=color, duration=5000)
                
                # Fechar janela de importação após sucesso
                if hasattr(self, 'import_dialog') and self.import_dialog:
                    self.app.page.close(self.import_dialog)
                    
            else:
                error_message = (
                    f"❌ Nenhum item foi importado!\n"
                    f"📊 Linhas processadas: {total_lines}\n"
                    f"📁 Arquivos analisados: {len(self.validated_files)}"
                )
                
                if errors:
                    error_message += f"\n🚨 Erros encontrados: {len(errors)}"
                    for i, error in enumerate(errors[:3], 1):  # Mostrar apenas os primeiros 3 erros
                        error_message += f"\n{i}. {error}"
                    
                    if len(errors) > 3:
                        error_message += f"\n... e mais {len(errors) - 3} erro(s)"
                
                self.app.show_custom_notification(error_message, color=ft.Colors.RED_400, duration=6000)
                
            # Log detalhado no console
            print(f"\n=== RESUMO DA IMPORTAÇÃO ===")
            print(f"Total de linhas: {total_lines}")
            print(f"Novos itens: {total_imported}")
            print(f"Itens atualizados: {total_updated}")
            print(f"Arquivos processados: {len(self.validated_files)}")
            print(f"Erros encontrados: {len(errors)}")
            if errors:
                print("\nDetalhes dos erros:")
                for i, error in enumerate(errors, 1):
                    print(f"{i}. {error}")
            print("=" * 30)
                
        except Exception as e:
            error_msg = f"💥 Erro crítico durante a importação: {str(e)}"
            print(f"ERRO CRÍTICO: {e}")
            self.app.show_custom_notification(error_msg, color=ft.Colors.RED_400, duration=6000)


class NotificationIconAnimator:
    """Classe para gerenciar animação dos ícones de notificação"""
    
    def __init__(self):
        self.animated_icons = {}  # Dicionário para controlar ícones animados
        self.animation_tasks = {}  # Tasks de animação ativas
    
    async def start_pulse_animation(self, icon_button, item_id):
        """Inicia animação de pulso com fade no ícone"""
        if item_id in self.animation_tasks:
            return  # Já está animando
            
        async def pulse():
            try:
                original_color = icon_button.icon_color
                while item_id in self.animated_icons:
                    # Fade out - ficar mais transparente/escuro
                    icon_button.icon_color = ft.Colors.ORANGE_200
                    icon_button.update()
                    await asyncio.sleep(0.5)
                    
                    # Fade in - voltar para cor original
                    if item_id in self.animated_icons:  # Verifica se ainda deve animar
                        icon_button.icon_color = ft.Colors.ORANGE
                        icon_button.update()
                        await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Erro na animação: {e}")
        
        self.animated_icons[item_id] = True
        self.animation_tasks[item_id] = asyncio.create_task(pulse())
    
    def stop_animation(self, icon_button, item_id):
        """Para a animação do ícone"""
        if item_id in self.animated_icons:
            del self.animated_icons[item_id]
        
        if item_id in self.animation_tasks:
            self.animation_tasks[item_id].cancel()
            del self.animation_tasks[item_id]
        
        # Restaura cor original
        icon_button.icon_color = ft.Colors.ORANGE
        icon_button.update()
    
    def cleanup(self):
        """Limpa todas as animações"""
        for task in self.animation_tasks.values():
            task.cancel()
        self.animation_tasks.clear()
        self.animated_icons.clear()

class DatabaseManager:
    """Classe para gerenciar operações no banco de dados"""
    
    def __init__(self, db_path='vpcr_database.db'):
        self.db_path = db_path
        self.create_todos_table()
        self.create_log_table()
    
    def get_connection(self):
        """Cria uma nova conexão com o banco de dados com timeout"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute('PRAGMA busy_timeout = 30000')  # 30 segundos de timeout
        conn.execute('PRAGMA journal_mode = WAL')    # Write-Ahead Logging para melhor concorrência
        return conn
    
    def create_todos_table(self):
        """Cria a tabela de todos no banco de dados se não existir"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS todos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id INTEGER NOT NULL,
                    description TEXT NOT NULL,
                    completed BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
    
    def create_log_table(self):
        """Cria a tabela de log para rastrear alterações"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS log_table (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    old_value TEXT,
                    new_value TEXT,
                    change_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    change_type TEXT DEFAULT 'update'
                )
            ''')
            conn.commit()
    

    
    def get_todos_for_item(self, item_id):
        """Busca todos os TODOs para um item específico"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, description, completed FROM todos WHERE item_id = ? ORDER BY created_at', (item_id,))
            return [{'id': row[0], 'description': row[1], 'completed': bool(row[2])} for row in cursor.fetchall()]
    
    def add_todo(self, item_id, description):
        """Adiciona um novo TODO"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('INSERT INTO todos (item_id, description) VALUES (?, ?)', (item_id, description))
            conn.commit()
            return cursor.lastrowid
    
    def update_todo(self, todo_id, description=None, completed=None):
        """Atualiza um TODO existente"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if description is not None:
                cursor.execute('UPDATE todos SET description = ? WHERE id = ?', (description, todo_id))
            if completed is not None:
                cursor.execute('UPDATE todos SET completed = ? WHERE id = ?', (completed, todo_id))
            conn.commit()
    
    def toggle_todo(self, todo_id):
        """Alterna o status de conclusão de um TODO"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE todos SET completed = NOT completed WHERE id = ?', (todo_id,))
            conn.commit()
    
    def delete_todo(self, todo_id):
        """Remove um TODO"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM todos WHERE id = ?', (todo_id,))
            conn.commit()
    
    def get_todos_count(self, item_id):
        """Retorna a contagem de TODOs para um item"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as total, SUM(CASE WHEN completed = 1 THEN 1 ELSE 0 END) as completed FROM todos WHERE item_id = ?', (item_id,))
            row = cursor.fetchone()
            return {'total': row[0], 'completed': row[1] or 0}
    
    def has_todos(self, item_id):
        """Verifica se um item tem TODOs"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM todos WHERE item_id = ?', (item_id,))
            return cursor.fetchone()[0] > 0
    
    def has_incomplete_todos(self, item_id):
        """Verifica se um item tem TODOs incompletos"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM todos WHERE item_id = ? AND completed = 0', (item_id,))
            return cursor.fetchone()[0] > 0
    
    def convert_date_format(self, date_str):
        """Converte data de m/d/yyyy para dd/mm/yyyy"""
        try:
            import pandas as pd
        except ImportError:
            pd = None
            
        if not date_str or (pd and pd.isna(date_str)):
            return ""
        
        try:
            if isinstance(date_str, str):
                # Se já está no formato dd/mm/yyyy, retorna como está
                if '/' in date_str and len(date_str.split('/')) == 3:
                    parts = date_str.split('/')
                    if len(parts[0]) <= 2 and len(parts[1]) <= 2 and len(parts[2]) == 4:
                        # Pode estar em m/d/yyyy
                        if int(parts[0]) > 12:  # Dia > 12, então está em d/m/yyyy
                            return date_str
                        else:
                            # Assumir m/d/yyyy e converter para dd/mm/yyyy
                            month, day, year = parts
                            return f"{day.zfill(2)}/{month.zfill(2)}/{year}"
                return date_str
            else:
                # Se for datetime do pandas
                return date_str.strftime('%d/%m/%Y')
        except Exception as e:
            print(f"Erro ao converter data '{date_str}': {e}")
            return str(date_str) if date_str else ""
    
    def log_change(self, item_id, field_name, old_value, new_value, change_type='update', conn=None):
        """Registra uma alteração no log"""
        # Só registra se houver mudança real
        if str(old_value) == str(new_value):
            return
        
        # Usar conexão fornecida ou criar nova
        if conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO log_table (item_id, field_name, old_value, new_value, change_type)
                VALUES (?, ?, ?, ?, ?)
            ''', (item_id, field_name, str(old_value) if old_value else '', 
                  str(new_value) if new_value else '', change_type))
        else:
            connection = None
            try:
                connection = self.get_connection()
                cursor = connection.cursor()
                cursor.execute('''
                    INSERT INTO log_table (item_id, field_name, old_value, new_value, change_type)
                    VALUES (?, ?, ?, ?, ?)
                ''', (item_id, field_name, str(old_value) if old_value else '', 
                      str(new_value) if new_value else '', change_type))
                connection.commit()
            except Exception as e:
                if connection:
                    connection.rollback()
                raise e
            finally:
                if connection:
                    connection.close()
    
    def get_item_from_db(self, item_id):
        """Busca um item específico do banco de dados"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM vpcr WHERE vpcr = ?', (item_id,))
            columns = [description[0] for description in cursor.description]
            row = cursor.fetchone()
            if row:
                return dict(zip(columns, row))
            return None
    
    def upsert_item(self, item_data):
        """Insere ou atualiza um item no banco de dados"""
        item_id = item_data.get('ID')
        if not item_id:
            return
            
        # Mapear campos do formato da aplicação para o formato do banco de dados
        db_field_mapping = {
            'ID': 'vpcr',
            'Title': 'vpcr_title',
            'Initiated Date': 'initiated_date',
            'Last Update': 'last_update',
            'Closed Date': 'closed_date',
            'Category': 'category_3_group',
            'Supplier': 'current_supplier',
            'PNs': 'items_affected',
            'Plants Affected': 'plants_affected',
            'Requestor': 'vpcr_requestor',
            'Sourcing Manager': 'sourcing_manager',
            'SQIE': 'sqie_s',
            'Continuity': 'continuity',
            'Status': 'vpcr_status',
            'RFQ': 'rfq',
            'DRA': 'dra',
            'DQR': 'dqr',
            'LOI': 'loi',
            'Tooling': 'tooling',
            'Drawing': 'drawing',
            'PO Alfa': 'po_alfa',
            'SR': 'sr_roc',
            'Deviation': 'deviation',
            'PO Beta': 'po_beta',
            'PPAP': 'ppap',
            'GBPA': 'gbpa',
            'EDI': 'edi',
            'SCR': 'scr_item_id',
            'Comments': 'comments',
            'Log': 'log',
            'Link': 'link_vpcr',
            'Type of VPCR': 'type_of_vpcr',
            'Proposed Supplier': 'proposed_supplier',
            'Category 2 (Area)': 'category_2_area',
            'Supporting Documentation': 'supporting_documentation',
            'Project Editor': 'project_editor',
            'Change Manager': 'change_manager',
            'Affected Items': 'items_affected',
            'Desired Production Date at Affected Plant(s)': 'desired_production_date',
            'SCR Item ID': 'scr_item_id'
        }
            
        # Usar uma única conexão para toda a operação
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Iniciar transação explícita
            cursor.execute('BEGIN IMMEDIATE')
            
            # Verificar se o item já existe
            cursor.execute('SELECT * FROM vpcr WHERE vpcr = ?', (item_id,))
            columns = [description[0] for description in cursor.description]
            row = cursor.fetchone()
            existing_item = dict(zip(columns, row)) if row else None
            
            # Converter dados para formato do banco
            db_data = {}
            for app_field, value in item_data.items():
                db_field = db_field_mapping.get(app_field, app_field.lower().replace(' ', '_'))
                db_data[db_field] = value
            
            if existing_item:
                # Atualizar item existente e registrar mudanças
                update_pairs = []
                update_values = []
                
                for db_field, new_value in db_data.items():
                    old_value = existing_item.get(db_field, '')
                    if str(old_value) != str(new_value):
                        update_pairs.append(f'{db_field} = ?')
                        update_values.append(new_value)
                        # Registrar mudança no log na mesma transação
                        cursor.execute('''
                            INSERT INTO log_table (item_id, field_name, old_value, new_value, change_type)
                            VALUES (?, ?, ?, ?, ?)
                        ''', (item_id, db_field, str(old_value) if old_value else '', 
                              str(new_value) if new_value else '', 'import_update'))
                
                if update_pairs:
                    update_sql = f'UPDATE vpcr SET {", ".join(update_pairs)} WHERE vpcr = ?'
                    update_values.append(item_id)
                    cursor.execute(update_sql, update_values)
            else:
                # Inserir novo item
                fields = list(db_data.keys())
                placeholders = ', '.join(['?' for _ in fields])
                field_names = ', '.join(fields)
                values = list(db_data.values())
                
                insert_sql = f'INSERT OR REPLACE INTO vpcr ({field_names}) VALUES ({placeholders})'
                cursor.execute(insert_sql, values)
                # Registrar criação no log na mesma transação
                cursor.execute('''
                    INSERT INTO log_table (item_id, field_name, old_value, new_value, change_type)
                    VALUES (?, ?, ?, ?, ?)
                ''', (item_id, 'ITEM_CREATED', '', 'Item criado via importação', 'import_create'))
            
            # Commit da transação
            conn.commit()
            
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                conn.close()
    
    def import_from_excel(self, file_path):
        """Importa dados do Excel comparando com dados existentes"""
        try:
            import pandas as pd
            import time
            
            # Ler o arquivo Excel
            df = pd.read_excel(file_path)
            
            # Mapear colunas do Excel para campos do banco
            column_mapping = {
                'VPCR Project ID': 'vpcr',  # Campo VPCR correto
                'VPCR Title': 'Title',
                'Initiated Date': 'Initiated Date',
                'Last Updated Date': 'Last Update',
                'Closed Date': 'Closed Date',
                'Category 3 (Group)': 'Category',
                'Current Supplier': 'Supplier',
                'Affected Items': 'PNs',
                'Plants Affected - Post CPIF Integration': 'Plants Affected',
                'VPCR Requestor': 'Requestor',
                'Sourcing Manager': 'Sourcing Manager',
                'SQIE(s)': 'SQIE',
                'VPCR Status': 'Status',
                'Type of VPCR': 'Type of VPCR',
                'Proposed Supplier': 'Proposed Supplier',
                'Category 2 (Area)': 'Category 2 (Area)',
                'Supporting Documentation': 'Supporting Documentation',
                'Project Editor': 'Project Editor',
                'Change Manager': 'Change Manager',
                'Desired Production Date at Affected Plant(s)': 'Desired Production Date at Affected Plant(s)',
                'SCR Item ID': 'SCR Item ID'
            }
            
            imported_count = 0
            updated_count = 0
            batch_size = 10  # Processar em lotes menores
            
            # Processar em lotes para evitar locks prolongados
            for batch_start in range(0, len(df), batch_size):
                batch_end = min(batch_start + batch_size, len(df))
                batch_df = df.iloc[batch_start:batch_end]
                
                for index, row in batch_df.iterrows():
                    try:
                        # Preparar dados do item
                        item_data = {}
                        
                        for excel_col, db_field in column_mapping.items():
                            if excel_col in row:
                                value = row[excel_col]
                                
                                # Converter datas
                                if 'Date' in excel_col:
                                    value = self.convert_date_format(value)
                                
                                # Tratar valores NaN
                                if pd.isna(value):
                                    value = ""
                                else:
                                    value = str(value).strip()
                                
                                # Processar campos que devem ser listas (separados por ;)
                                if db_field in ['PNs', 'Plants Affected'] and value:
                                    # Quebrar por ";" e limpar espaços
                                    value_list = [item.strip() for item in value.split(';') if item.strip()]
                                    # Manter como string para compatibilidade, mas formatada como lista
                                    value = '; '.join(value_list)
                                
                                item_data[db_field] = value
                        
                        # Verificar se tem ID válido
                        if not item_data.get('ID'):
                            print(f"Linha {index + 1}: ID não encontrado, pulando...")
                            continue
                        
                        # Verificar se item já existe (usando método separado para evitar conflitos)
                        existing = None
                        retry_count = 3
                        for attempt in range(retry_count):
                            try:
                                existing = self.get_item_from_db(item_data['ID'])
                                break
                            except Exception as e:
                                if 'locked' in str(e).lower() and attempt < retry_count - 1:
                                    time.sleep(0.1 * (attempt + 1))  # Espera exponencial
                                    continue
                                else:
                                    raise e
                        
                        # Fazer upsert com retry
                        for attempt in range(retry_count):
                            try:
                                self.upsert_item(item_data)
                                break
                            except Exception as e:
                                if 'locked' in str(e).lower() and attempt < retry_count - 1:
                                    time.sleep(0.1 * (attempt + 1))  # Espera exponencial
                                    continue
                                else:
                                    raise e
                        
                        if existing:
                            updated_count += 1
                        else:
                            imported_count += 1
                            
                    except Exception as e:
                        print(f"Erro ao processar linha {index + 1}: {e}")
                        continue
                
                # Pequena pausa entre lotes para permitir outras operações
                time.sleep(0.01)
            
            return {
                'success': True,
                'imported': imported_count,
                'updated': updated_count,
                'total_processed': imported_count + updated_count
            }
            
        except Exception as e:
            print(f"Erro na importação: {e}")
            return {
                'success': False,
                'error': str(e),
                'imported': 0,
                'updated': 0,
                'total_processed': 0
            }
    
    def get_all_items(self):
        """Retorna todos os itens do banco de dados"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM vpcr')
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            
            # Converter para o formato esperado pela aplicação
            formatted_items = []
            for row in rows:
                item_dict = dict(zip(columns, row))
                # Mapear campos do banco para o formato esperado
                formatted_item = {
                    'ID': item_dict.get('vpcr', ''),
                    'vpcr': item_dict.get('vpcr', ''),  # Campo VPCR para o título do card
                    'Title': item_dict.get('vpcr_title', ''),
                    'Initiated Date': item_dict.get('initiated_date', ''),
                    'Last Update': item_dict.get('last_update', ''),
                    'Closed Date': item_dict.get('closed_date', ''),
                    'Category': item_dict.get('category_3_group', ''),
                    'Supplier': item_dict.get('current_supplier', ''),
                    'PNs': item_dict.get('items_affected', ''),
                    'Plants Affected': item_dict.get('plants_affected', ''),
                    'Requestor': item_dict.get('vpcr_requestor', ''),
                    'Sourcing Manager': item_dict.get('sourcing_manager', ''),
                    'SQIE': item_dict.get('sqie_s', ''),
                    'Continuity': item_dict.get('continuity', ''),
                    'Status': item_dict.get('vpcr_status', ''),
                    'RFQ': item_dict.get('rfq', ''),
                    'DRA': item_dict.get('dra', ''),
                    'DQR': item_dict.get('dqr', ''),
                    'LOI': item_dict.get('loi', ''),
                    'Tooling': item_dict.get('tooling', ''),
                    'Drawing': item_dict.get('drawing', ''),
                    'PO Alfa': item_dict.get('po_alfa', ''),
                    'SR': item_dict.get('sr_roc', ''),
                    'Deviation': item_dict.get('deviation', ''),
                    'PO Beta': item_dict.get('po_beta', ''),
                    'PPAP': item_dict.get('ppap', ''),
                    'GBPA': item_dict.get('gbpa', ''),
                    'EDI': item_dict.get('edi', ''),
                    'SCR': item_dict.get('scr_item_id', ''),
                    'Comments': item_dict.get('comments', ''),
                    'Log': item_dict.get('log', ''),
                    'Link': item_dict.get('link_vpcr', ''),
                    'Type of VPCR': item_dict.get('type_of_vpcr', ''),
                    'Current Supplier': item_dict.get('current_supplier', ''),
                    'Proposed Supplier': item_dict.get('proposed_supplier', ''),
                    'Category 3 (Group)': item_dict.get('category_3_group', ''),
                    'Category 2 (Area)': item_dict.get('category_2_area', ''),
                    'Supporting Documentation': item_dict.get('supporting_documentation', ''),
                    'Project Editor': item_dict.get('project_editor', ''),
                    'Change Manager': item_dict.get('change_manager', ''),
                    'Affected Items': item_dict.get('items_affected', ''),
                    'Desired Production Date at Affected Plant(s)': item_dict.get('desired_production_date', ''),
                    'SCR Item ID': item_dict.get('scr_item_id', '')
                }
                
                # Processar campos que devem ser listas (quebrados por ;)
                for field in ['PNs', 'Plants Affected']:
                    if formatted_item[field]:
                        # Quebrar por ";" e criar lista limpa
                        items_list = [item.strip() for item in formatted_item[field].split(';') if item.strip()]
                        # Manter como string formatada para compatibilidade
                        formatted_item[field] = '; '.join(items_list) if items_list else ''
                formatted_items.append(formatted_item)
            
            return formatted_items
    
    def get_change_log(self, item_id=None, limit=100):
        """Retorna o log de alterações"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if item_id:
                cursor.execute('''
                    SELECT * FROM log_table 
                    WHERE item_id = ? 
                    ORDER BY change_date DESC 
                    LIMIT ?
                ''', (item_id, limit))
            else:
                cursor.execute('''
                    SELECT * FROM log_table 
                    ORDER BY change_date DESC 
                    LIMIT ?
                ''', (limit,))
            
            columns = [description[0] for description in cursor.description]
            rows = cursor.fetchall()
            return [dict(zip(columns, row)) for row in rows]

class ThemeManager:
    """Gerenciador de temas da aplicação"""
    
    def __init__(self):
        self.themes = {
            "dark": {
                "primary": "#181818",
                "secondary": "#1e1e1e",
                "surface": "#2d2d2d",
                "on_surface": "#ffffff",
                "on_primary": "#ffffff",
                "accent": "#5893ff",
                "card_bg": "#2d2d2d",
                "border": "#3d3d3d",
                "text_primary": "#ffffff",           # Texto fora de containers
                "text_secondary": "#b3b3b3",         # Texto secundário fora de containers
                "text_container_primary": "#ffffff",    # Texto principal dentro de containers
                "text_container_secondary": "#b3b3b3",  # Texto secundário dentro de containers
                "field_bg": "#2d2d2d",
                "field_text": "#ffffff",
                "field_border": "#444444",
                "cor_font_settings": "#ffffff",
                "selected_card": "#323550"       # Cor para card selecionado
            },
            "dracula": {
                "primary": "#282a36",
                "secondary": "#44475a",
                "surface": "#6272a4",
                "on_surface": "#f8f8f2",
                "on_primary": "#f8f8f2",
                "accent": "#a676ff",
                "card_bg": "#44475a",
                "border": "#6272a4",
                "text_primary": "#f8f8f2",           # Texto fora de containers
                "text_secondary": "#adb8bb",          # Texto secundário fora de containers
                "text_container_primary": "#f8f8f2",    # Texto principal dentro de containers
                "text_container_secondary": "#8be9fd",  # Texto secundário dentro de containers
                "field_bg": "#4a4d60",               # Fundo do campo igual à cor da borda
                "field_text": "#8be9fd",
                "field_border": "#4a4d60",           # Borda mais próxima da cor do container
                "cor_font_settings": "#f8f8f2",       # Cor específica para textos em settings (laranja clara)
                "selected_card": "#6272a4"       # Cor para card selecionado
            },
            "light_dracula": {
                    # Light Dracula Azul: variante clara com base branco-azulada e acentos roxos
                    # Mantém contraste adequado e suavidade em superfícies elevadas
                    "primary": "#A3A3A3",             # Branco azulado (base da UI)
                    "secondary": "#44475a",
                    "surface": "#6272a4",            # Superfície elevada (cards e painéis)
                    "on_surface": "#373a46",          # Texto sobre surface
                    "on_primary": "#4c4d52",          # Texto sobre primary
                    "accent": "#ac7eec",              # Roxo característico Dracula
                    "card_bg": "#44475a",            # Fundo de cards, levemente mais escuro que primary
                    "border": "#B7C3D6",              # Bordas azuladas discretas
                    "text_primary": "#f8f8f2",           # Texto fora de containers
                    "text_secondary": "#adb8bb",          # Texto secundário fora de containers
                    "text_container_primary": "#DAD8D8",    # Texto principal dentro de containers
                    "text_container_secondary": "#8be9fd", # Texto secundário dentro de containers
                    "field_bg": "#4a4d60",               # Fundo do campo igual à cor da borda
                    "field_text": "#8be9fd",          # Texto dos campos
                    "field_border": "#4a4d60",        # Bordas discretas azuladas
                    "cor_font_settings": "#bbbbbb",   # Texto em configurações
                    "selected_card": "#6272a4"       # Destaque de seleção com leve tom azul-violeta
                }
        }
        self.current_theme = "dark"
        self.font_size = 14  # Tamanho padrão da fonte
        self.load_theme()
        self.load_font_size()
    
    def get_theme_colors(self):
        """Retorna as cores do tema atual"""
        return self.themes[self.current_theme]
    
    def set_theme(self, theme_name):
        """Define o tema atual"""
        if theme_name in self.themes:
            self.current_theme = theme_name
            self.save_theme()
    
    def save_theme(self):
        """Salva o tema atual em arquivo"""
        try:
            # Salvar em %APPDATA%/VPCR App/themes/theme_config.json
            appdata = os.getenv('APPDATA') or os.path.expanduser('~')
            config_dir = os.path.join(appdata, 'VPCR App', 'themes')
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, 'theme_config.json')
            with open(config_path, "w", encoding='utf-8') as f:
                json.dump({"theme": self.current_theme}, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def load_theme(self):
        """Carrega o tema salvo"""
        try:
            appdata = os.getenv('APPDATA') or os.path.expanduser('~')
            config_dir = os.path.join(appdata, 'VPCR App', 'themes')
            config_path = os.path.join(config_dir, 'theme_config.json')
            if os.path.exists(config_path):
                with open(config_path, "r", encoding='utf-8') as f:
                    config = json.load(f)
                    self.current_theme = config.get("theme", "dark")
        except:
            pass
    
    def set_font_size(self, size):
        """Define o tamanho da fonte"""
        self.font_size = size
        self.save_font_size()
    
    def save_font_size(self):
        """Salva o tamanho da fonte em arquivo"""
        try:
            appdata = os.getenv('APPDATA') or os.path.expanduser('~')
            config_dir = os.path.join(appdata, 'VPCR App', 'themes')
            os.makedirs(config_dir, exist_ok=True)
            config_path = os.path.join(config_dir, 'font_config.json')
            with open(config_path, "w", encoding='utf-8') as f:
                json.dump({"font_size": self.font_size}, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def load_font_size(self):
        """Carrega o tamanho da fonte salvo"""
        try:
            appdata = os.getenv('APPDATA') or os.path.expanduser('~')
            config_dir = os.path.join(appdata, 'VPCR App', 'themes')
            config_path = os.path.join(config_dir, 'font_config.json')
            if os.path.exists(config_path):
                with open(config_path, "r", encoding='utf-8') as f:
                    config = json.load(f)
                    self.font_size = config.get("font_size", 14)
        except:
            self.font_size = 14

class VPCRApp:
    def __init__(self):
        self.theme_manager = ThemeManager()
        self.db_manager = DatabaseManager()
        self.icon_animator = NotificationIconAnimator()
        # Gerenciador de importação de arquivos
        self.file_import_manager = FileImportManager(self)
        # Dicionário para rastrear ícones animados
        self.animated_icons = {}
        # Cabeçalho do 'banco de dados' — deve corresponder ao Controle VPCR.xlsb
        self.db_headers = [
            "ID",
            "Title",
            "Description",
            "Status",
            "Sourcing Manager",
            "Supplier",
            "Requestor",
            "Continuity",
        ]

        # Carregar dados do banco de dados ao inicializar
        self.sample_data = self.load_data_from_db()
        self.filtered_data = self.sample_data.copy()
        # Campos visíveis nos cards (configurável nas Settings)
        self.visible_fields = ["Title", "Description", "Status", "Sourcing Manager", "Supplier"]
        # Carregar configuração persistida de campos visíveis (se existir)
        self.load_visible_fields()
        # Estado para seleção/exportação de cards
        self.card_select_mode = False
        self.card_selection = set()  # IDs selecionados para exportação
        
        # Campos detalhados (valores mostrados no painel direito)
        # Inicializar com valores de exemplo; chaves seguem os rótulos originais
        self.detail_fields = {
            # VPCR Overview
            "Title": "Item 1",
            "Initiated Date": "2025-01-01",
            "Last Update": "2025-01-10",
            "Closed Date": "",
            "Category": "Category A", 
            "Supplier": "Supplier A",
            "PNs": "PN-123; PN-456",
            "Plants Affected": "Plant A",
            # Request & Responsibility
            "Requestor": "John",
            "Sourcing": "Alice",
            "SQIE": "SQIE-1",
            "Continuity": "High",
            # Documentation
            "RFQ": "Yes",
            "DRA": "No",
            "DQR": "No",
            "LOI": "No",
            "Tooling": "N/A",
            "Drawing": "Rev A",
            "PO Alfa": "",
            "SR": "",
            "Deviation": "",
            "PO Beta": "",
            "PPAP": "",
            "GBPA": "",
            "EDI": "",
            "SCR": "",
            # L2 fields
            "Comments": "",
            "Log": "2025-01-01 - Created\n2025-01-10 - Updated"
        }
        # Item selecionado atualmente
        self.selected_item = None
        self.selected_item_id = None
        
        # Filtro para mostrar apenas cards com TODOs ativos
        self.show_only_active_todos = False
        
    def initialize_icon_animations(self):
        """Inicializa as animações dos ícones para itens com TODOs"""
        for item in self.sample_data:
            item_id = item.get("ID")
            if self.db_manager.has_todos(item_id):
                # Como os cards ainda não foram criados, a animação será iniciada 
                # no método create_card quando o card for criado
                pass
    
    def update_icon_animations(self):
        """Atualiza as animações dos ícones após mudanças nos TODOs"""
        # Atualizar apenas os itens que não devem mais ser animados
        active_ids = {item.get("ID") for item in self.sample_data if self.db_manager.has_incomplete_todos(item.get("ID"))}
        for item_id in list(self.animated_icons.keys()):
            if item_id not in active_ids:
                try:
                    btn = self.animated_icons[item_id]
                    btn.opacity = 1.0
                except Exception:
                    pass
                del self.animated_icons[item_id]
        
        # Atualizar lista de cards para refletir mudanças nos ícones
        if hasattr(self, 'card_list'):
            self.update_card_list()
            if hasattr(self, 'page'):
                self.page.update()
    
    def start_icon_animation(self, icon_button, item_id):
        """Inicia animação síncrona do ícone com fade melhorado"""
        import time
        fade_steps = 10  # Número de passos para fade suave
        
        while True:  # Continuar animação enquanto o item tiver TODOs incompletos
            try:
                # Verificar se ainda deve animar este item
                if item_id not in self.animated_icons:
                    break
                
                # Obter a referência mais atualizada do botão
                current_btn = self.animated_icons.get(item_id)
                if current_btn is None:  # O botão foi removido do dicionário
                    break
                    
                # Usar sempre a referência mais atual
                icon_button = current_btn
                
                # Fade out gradual
                for step in range(fade_steps):
                    # Verificar a cada step se deve parar
                    if item_id not in self.animated_icons:
                        # Resetar opacidade antes de sair
                        current_btn = self.animated_icons.get(item_id)
                        if current_btn:  # Se ainda existe uma referência
                            current_btn.opacity = 1.0
                            if hasattr(self, 'page') and self.page:
                                self.page.update()
                        return
                    
                    # Obter referência atualizada
                    current_btn = self.animated_icons.get(item_id)
                    if not current_btn:  # Botão removido durante animação
                        return
                        
                    opacity = 1.0 - (step / fade_steps * 0.7)  # De 1.0 até 0.3
                    current_btn.opacity = opacity
                    if hasattr(self, 'page') and self.page:
                        self.page.update()
                    time.sleep(0.03)  # 30ms por step = 300ms total para fade out
                
                # Verificar antes da pausa
                if item_id not in self.animated_icons:
                    current_btn = self.animated_icons.get(item_id)
                    if current_btn:
                        current_btn.opacity = 1.0
                        if hasattr(self, 'page') and self.page:
                            self.page.update()
                    return
                
                # Manter opacidade baixa por um momento
                time.sleep(0.1)
                
                # Fade in gradual
                for step in range(fade_steps):
                    # Verificar a cada step se deve parar
                    if item_id not in self.animated_icons:
                        # Resetar opacidade antes de sair
                        current_btn = self.animated_icons.get(item_id)
                        if current_btn:
                            current_btn.opacity = 1.0
                            if hasattr(self, 'page') and self.page:
                                self.page.update()
                        return
                    
                    # Obter referência atualizada
                    current_btn = self.animated_icons.get(item_id)
                    if not current_btn:  # Botão removido durante animação
                        return
                        
                    opacity = 0.3 + (step / fade_steps * 0.7)  # De 0.3 até 1.0
                    current_btn.opacity = opacity
                    if hasattr(self, 'page') and self.page:
                        self.page.update()
                    time.sleep(0.03)  # 30ms por step = 300ms total para fade in
                
                # Verificar antes da pausa final
                if item_id not in self.animated_icons:
                    current_btn = self.animated_icons.get(item_id)
                    if current_btn:
                        current_btn.opacity = 1.0
                        if hasattr(self, 'page') and self.page:
                            self.page.update()
                    return
                
                # Pausa antes do próximo ciclo
                time.sleep(0.8)  # Pausa entre pulsações
                
            except Exception as e:
                # Se ocorrer erro, tentar continuar se for um erro transitório
                time.sleep(0.5)
                
                # Se o item não está mais no dicionário, parar a animação
                if item_id not in self.animated_icons:
                    break
                
        # Garantir que a opacidade seja resetada quando o loop terminar
        try:
            icon_button.opacity = 1.0
            if hasattr(self, 'page') and self.page:
                self.page.update()
        except Exception:
            pass
        
    def stop_all_animations(self):
        """Para todas as animações ativas"""
        # Limpar o dicionário de ícones animados para parar as animações
        animated_items = list(self.animated_icons.keys())
        for item_id in animated_items:
            # Resetar opacidade do ícone
            if item_id in self.animated_icons:
                icon_button = self.animated_icons[item_id]
                icon_button.opacity = 1.0
        
        # Limpar o dicionário para parar as animações
        self.animated_icons.clear()
        
        # Atualizar a página para aplicar as mudanças
        if hasattr(self, 'page') and self.page:
            self.page.update()
    
    def load_data_from_db(self):
        """Carrega dados do banco de dados na inicialização"""
        try:
            # Buscar itens do banco de dados
            db_items = self.db_manager.get_all_items()
            
            if db_items:
                print(f"Dados carregados na inicialização: {len(db_items)} itens do banco de dados")
                return db_items
            else:
                print("Nenhum item encontrado no banco de dados, usando dados de exemplo")
                # Retornar dados de exemplo se não houver dados no banco
                return [
                    {"ID": 1, "Title": "Item 1", "Description": "Descrição do item 1", "Status": "Ativo", "Sourcing Manager": "Alice", "Supplier": "Supplier A", "Requestor": "John", "Continuity": "High", "vpcr": "VPCR00001"},
                    {"ID": 2, "Title": "Item 2", "Description": "Descrição do item 2", "Status": "Inativo", "Sourcing Manager": "Bob", "Supplier": "Supplier B", "Requestor": "Mary", "Continuity": "Low", "vpcr": "VPCR00002"},
                    {"ID": 3, "Title": "Item 3", "Description": "Descrição do item 3", "Status": "Ativo", "Sourcing Manager": "Alice", "Supplier": "Supplier C", "Requestor": "Peter", "Continuity": "Medium", "vpcr": "VPCR00003"},
                    {"ID": 4, "Title": "Item 4", "Description": "Descrição do item 4", "Status": "Pendente", "Sourcing Manager": "Carlos", "Supplier": "Supplier A", "Requestor": "John", "Continuity": "High", "vpcr": "VPCR00004"},
                    {"ID": 5, "Title": "Item 5", "Description": "Outro item", "Status": "Ativo", "Sourcing Manager": "Diana", "Supplier": "Supplier B", "Requestor": "Mary", "Continuity": "Low", "vpcr": "VPCR00005"},
                ]
                
        except Exception as e:
            print(f"Erro ao carregar dados do banco na inicialização: {e}")
            # Retornar dados de exemplo em caso de erro
            return [
                {"ID": 1, "Title": "Item 1", "Description": "Descrição do item 1", "Status": "Ativo", "Sourcing Manager": "Alice", "Supplier": "Supplier A", "Requestor": "John", "Continuity": "High", "vpcr": "VPCR00001"},
                {"ID": 2, "Title": "Item 2", "Description": "Descrição do item 2", "Status": "Inativo", "Sourcing Manager": "Bob", "Supplier": "Supplier B", "Requestor": "Mary", "Continuity": "Low", "vpcr": "VPCR00002"},
            ]

    def refresh_data_from_db(self):
        """Recarrega os dados do banco de dados para a aplicação"""
        try:
            # Buscar itens do banco de dados
            db_items = self.db_manager.get_all_items()
            
            if db_items:
                # Atualizar sample_data com dados do banco
                self.sample_data = db_items
                # Atualizar dados filtrados
                self.filter_data()
                # Atualizar lista de cards
                self.update_card_list()
                # Atualizar opções de filtros
                self.populate_filter_options()
                print(f"Dados recarregados: {len(db_items)} itens do banco de dados")
            else:
                print("Nenhum item encontrado no banco de dados")
                
        except Exception as e:
            print(f"Erro ao recarregar dados do banco: {e}")
    
    def refresh_data_from_db(self):
        """Recarrega os dados do banco de dados após importação"""
        try:
            # Buscar todos os itens do banco de dados
            db_items = self.db_manager.get_all_items()
            
            if db_items:
                # Atualizar sample_data com dados do banco
                self.sample_data = db_items
                # Atualizar dados filtrados
                self.filter_data()
                # Atualizar lista de cards
                self.update_card_list()
                # Atualizar opções de filtros
                self.populate_filter_options()
                print(f"Dados atualizados: {len(db_items)} itens do banco de dados")
            else:
                print("Nenhum item encontrado no banco de dados")
                
        except Exception as e:
            print(f"Erro ao atualizar dados do banco: {e}")
        
    def main(self, page: ft.Page):
        self.page = page
        self.page.title = "VPCR App"
        self.page.window_min_width = 1200
        self.page.window_min_height = 800
        
        # Aplicar tema inicial
        self.apply_theme()
        
        # Criar componentes
        self.create_components()
        
        # Inicializar animações dos ícones para itens com TODOs
        self.initialize_icon_animations()
        
        # Adicionar o painel dropdown ao overlay da página para ficar suspenso
        self.page.overlay.append(self.dropdown_panel_container)
        
        # Área de notificação simples (SnackBar custom minimalista)
        self._notification_text = ft.Text("", color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD)
        self._notification_bar = ft.Container(
            content=ft.Row([
                self._notification_text,
                ft.IconButton(icon=ft.Icons.CLOSE, icon_color=ft.Colors.WHITE, tooltip="Fechar", on_click=lambda e: self.hide_notification())
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            visible=False,
            bgcolor=ft.Colors.BLUE_600,
            padding=10,
            border_radius=8
        )

        # Guardar referência do timeout para cancelar se necessário
        self._notification_timer = None

        # Função interna para criar tabs (facilita futura reorganização)
        tabs_control = ft.Tabs(
            tabs=[
                ft.Tab(text="VPCR", content=self.create_vpcr_tab()),
                ft.Tab(text="Settings", content=self.create_settings_tab())
            ],
            selected_index=0,
            animation_duration=300,
            label_color=self.theme_manager.get_theme_colors()["accent"],
            indicator_color=self.theme_manager.get_theme_colors()["accent"]
        )

        # Ajustar barra para overlay (remover visibilidade de layout)
        self._notification_bar.visible = False
        self._notification_bar.padding = 12
        self._notification_bar.margin = 0
        self._notification_bar.width = 420

        # Definir coordenadas absolutas diretamente (Stack aceita top/right nos filhos)
        self._notification_bar.top = 12
        self._notification_bar.right = 12

        self._overlay_stack = ft.Stack(
            controls=[
                ft.Container(
                    content=tabs_control,
                    bgcolor=self.theme_manager.get_theme_colors()["primary"],
                    expand=True,
                    padding=10
                ),
                self._notification_bar
            ],
            expand=True,
            clip_behavior=ft.ClipBehavior.NONE
        )

        self.page.add(self._overlay_stack)

    def notify(self, message: str, kind: str = "info", auto_hide: int = 3000):
        """Exibe uma notificação simples no topo.
        kind: info | success | error | warn
        auto_hide: ms (0 = não esconder automaticamente)
        """
        color_map = {
            "info": ft.Colors.BLUE_600,
            "success": ft.Colors.GREEN_600,
            "error": ft.Colors.RED_600,
            "warn": ft.Colors.ORANGE_600
        }
        bgcolor = color_map.get(kind, ft.Colors.BLUE_600)
        print(f"[NOTIFY] kind={kind} msg={message}")
        try:
            self._notification_text.value = message
            self._notification_bar.bgcolor = bgcolor
            self._notification_bar.visible = True
            # Garantir que o container de notificação está no Stack (último para ficar por cima)
            if self._notification_bar not in self._overlay_stack.controls:
                self._overlay_stack.controls.append(self._notification_bar)
            else:
                # mover para topo se não for último
                idx = self._overlay_stack.controls.index(self._notification_bar)
                if idx != len(self._overlay_stack.controls) - 1:
                    self._overlay_stack.controls.pop(idx)
                    self._overlay_stack.controls.append(self._notification_bar)
            self._overlay_stack.update()
            if self.page:
                self.page.update()
        except Exception as e:
            print(f"Falha ao exibir notificação: {e}")

        # Cancelar timer anterior
        if self._notification_timer:
            try:
                self._notification_timer.cancel()
            except Exception:
                pass
            self._notification_timer = None

        if auto_hide and auto_hide > 0:
            import threading
            def hide_later():
                import time
                time.sleep(auto_hide/1000)
                self.hide_notification()
            self._notification_timer = threading.Thread(target=hide_later, daemon=True)
            self._notification_timer.start()

    def hide_notification(self):
        """Esconde a notificação se visível"""
        try:
            if self._notification_bar.visible:
                self._notification_bar.visible = False
                # Manter espaço zero (não empurra layout por ser overlay)
                if self.page:
                    self._notification_bar.update()
                    self.page.update()
        except Exception as e:
            print(f"Erro ao esconder notificação: {e}")

    # Substituir métodos antigos chamando notify
    def show_custom_notification(self, message, color=ft.Colors.BLUE_400, duration=3000):
        # Compat: mapear cor básica para tipo
        kind = "info"
        if color == ft.Colors.GREEN_500:
            kind = "success"
        elif color == ft.Colors.RED_500:
            kind = "error"
        elif color == ft.Colors.ORANGE_500:
            kind = "warn"
        self.notify(message, kind=kind, auto_hide=duration)
    
    def apply_theme(self):
        """Aplica o tema atual à página"""
        colors = self.theme_manager.get_theme_colors()
        self.page.bgcolor = colors["primary"]
        self.page.theme = ft.Theme(
            color_scheme=ft.ColorScheme(
                primary=colors["accent"],
                background=colors["primary"],
                surface=colors["surface"],
                on_surface=colors["on_surface"]
            )
        )

    # ===================== Persistência de Campos Visíveis =====================
    def save_visible_fields(self):
        """Salva a lista de campos visíveis em arquivo JSON no diretório de settings do app."""
        try:
            appdata = os.getenv('APPDATA') or os.path.expanduser('~')
            settings_dir = os.path.join(appdata, 'VPCR App', 'settings')
            os.makedirs(settings_dir, exist_ok=True)
            path = os.path.join(settings_dir, 'visible_fields.json')
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({"visible_fields": self.visible_fields}, f, ensure_ascii=False, indent=2)
        except Exception:
            pass  # Falhar silenciosamente para não quebrar a UI

    def load_visible_fields(self):
        """Carrega os campos visíveis salvos anteriormente (se existir)."""
        try:
            appdata = os.getenv('APPDATA') or os.path.expanduser('~')
            settings_dir = os.path.join(appdata, 'VPCR App', 'settings')
            path = os.path.join(settings_dir, 'visible_fields.json')
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    loaded = data.get('visible_fields', [])
                    # Validar contra headers disponíveis (exceto ID)
                    allowed = [h for h in self.db_headers if h != 'ID']
                    # Manter ordem conforme db_headers original
                    self.visible_fields = [h for h in self.db_headers if h in loaded and h != 'ID']
                    # Garantir fallback mínimo
                    if not self.visible_fields:
                        self.visible_fields = ["Title", "Description", "Status", "Sourcing Manager", "Supplier"]
        except Exception:
            pass
    
    def create_components(self):
        """Cria os componentes da interface"""
        colors = self.theme_manager.get_theme_colors()
        
        # --- filtros com multiseleção usando Chips ---
        # containers para chips de multiseleção
        # Larguras uniformes para todos os filtros
        uniform_width = 160
        self.filter_widths = {
            "VPCR": uniform_width,
            "Sourcing Manager": uniform_width,
            "Status": uniform_width,
            "Supplier": uniform_width,
            "Requestor": uniform_width,
            "Continuity": uniform_width,
        }
        self.filter_order = [
            "VPCR",
            "Sourcing Manager",
            "Status",
            "Supplier",
            "Requestor",
            "Continuity",
        ]
        # Define uma altura padronizada para todos os filtros
        filter_height = 38  # Altura fixa para todos os filtros
        
        self.filter_vpcr_chips = ft.Container(
            content=ft.Text("VPCR: Carregando...", size=12, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
            bgcolor=colors["field_bg"],
            border=ft.border.all(1, colors["field_border"]),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            width=uniform_width,
            height=filter_height
        )
        
        self.filter_sourcing_manager_chips = ft.Container(
            content=ft.Text("Sourcing Manager: Carregando...", size=12, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
            bgcolor=colors["field_bg"],
            border=ft.border.all(1, colors["field_border"]),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            width=uniform_width,
            height=filter_height
        )
        
        self.filter_status_chips = ft.Container(
            content=ft.Text("Status: Carregando...", size=12, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
            bgcolor=colors["field_bg"],
            border=ft.border.all(1, colors["field_border"]),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            width=uniform_width,
            height=filter_height
        )
        
        self.filter_supplier_chips = ft.Container(
            content=ft.Text("Supplier: Carregando...", size=12, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
            bgcolor=colors["field_bg"],
            border=ft.border.all(1, colors["field_border"]),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            width=uniform_width,
            height=filter_height
        )
        
        self.filter_requestor_chips = ft.Container(
            content=ft.Text("Requestor: Carregando...", size=12, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
            bgcolor=colors["field_bg"],
            border=ft.border.all(1, colors["field_border"]),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            width=uniform_width,
            height=filter_height
        )
        
        self.filter_continuity_chips = ft.Container(
            content=ft.Text("Continuity: Carregando...", size=12, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
            bgcolor=colors["field_bg"],
            border=ft.border.all(1, colors["field_border"]),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            width=uniform_width,
            height=filter_height
        )
        
        # armazenamento das seleções
        self.filter_selections = {
            "VPCR": set(),
            "Sourcing Manager": set(),
            "Status": set(),
            "Supplier": set(),
            "Requestor": set(),
            "Continuity": set()
        }
        # Popular opções únicas a partir dos dados
        self.populate_filter_options()

        # Switch para mostrar apenas TODOs ativos
        def on_todos_filter_change(e):
            self.show_only_active_todos = e.control.value
            
            # Aplicar filtro (isso recria os cards) sem parar as animações
            self.filter_data()
        
        self.todos_filter_switch = ft.Switch(
            label="Apenas TODOs ativos",
            value=self.show_only_active_todos,
            on_change=on_todos_filter_change
        )

        # Painel dropdown customizado (inicialmente oculto)
        # Agora configurado para usar no page.overlay (suspenso)
        self.dropdown_panel_container = ft.Container(
            visible=False,
            content=None,
            # Para janela suspensa com posicionamento absoluto no overlay
            left=0,
            top=0
        )
        self.dropdown_open_for = None  # nome do campo atualmente aberto
    
    def filter_data(self, e=None):
        """Filtra os dados baseado nos filtros ativos"""
        # filtros de multiseleção (conjuntos de valores)
        vpcr_sel = self.filter_selections.get("VPCR", set())
        sm_sel = self.filter_selections.get("Sourcing Manager", set())
        status_multi_sel = self.filter_selections.get("Status", set())
        supplier_sel = self.filter_selections.get("Supplier", set())
        requestor_sel = self.filter_selections.get("Requestor", set())
        continuity_sel = self.filter_selections.get("Continuity", set())
        
        # Salvar IDs com animações antes de filtrar para preservá-las
        animated_before_filter = set(self.animated_icons.keys())
        
        self.filtered_data = []
        for item in self.sample_data:
            def matches_multi(selected_set, value):
                if not selected_set:  # nada selecionado = mostrar todos
                    return True
                return value in selected_set

            vpcr_match = matches_multi(vpcr_sel, item.get("vpcr", ""))
            sm_match = matches_multi(sm_sel, item.get("Sourcing Manager", ""))
            status_multi_match = matches_multi(status_multi_sel, item.get("Status", ""))
            supplier_match = matches_multi(supplier_sel, item.get("Supplier", ""))
            requestor_match = matches_multi(requestor_sel, item.get("Requestor", ""))
            continuity_match = matches_multi(continuity_sel, item.get("Continuity", ""))
            
            # Filtro de TODOs ativos
            todos_match = True
            if self.show_only_active_todos:
                item_id = item.get("ID")
                has_incomplete_todos = self.db_manager.has_incomplete_todos(item_id)
                todos_match = has_incomplete_todos
            
            if vpcr_match and sm_match and status_multi_match and supplier_match and requestor_match and continuity_match and todos_match:
                self.filtered_data.append(item)
        
        # Mostrar notificação do resultado do filtro
        if hasattr(self, 'page') and e is not None:  # Não mostrar na inicialização
            count = len(self.filtered_data)
            message = f"Filtro aplicado: {count} item{'s' if count != 1 else ''} encontrado{'s' if count != 1 else ''}"
            
            snack_bar = ft.SnackBar(
                content=ft.Text(message),
                duration=2000  # 2 segundos
            )
            self.page.snack_bar = snack_bar
            snack_bar.open = True
            self.page.update()
        
        self.update_card_list(preserve_scroll=True)
    
    def create_card(self, item):
        """Cria um card para um item"""
        colors = self.theme_manager.get_theme_colors()
        base_font = getattr(self.theme_manager, 'font_size', 14)
        # Inicializar estruturas de estado para tracking de alterações se ainda não existirem
        if not hasattr(self, 'dirty_items'):
            self.dirty_items = set()  # IDs de items modificados e não salvos
        if not hasattr(self, 'card_save_buttons'):
            self.card_save_buttons = {}  # item_id -> referência de botão salvar
        # obter status e cor do status
        status_val = item.get("Status", "")
        status_color = {
            "Ativo": ft.Colors.GREEN,
            "Inativo": ft.Colors.RED,
            "Pendente": ft.Colors.ORANGE
        }.get(status_val, ft.Colors.GREY)

        # Verificar se este item está selecionado
        is_selected = self.selected_item_id == item.get("ID")
        card_bg_color = colors["selected_card"] if is_selected else colors["card_bg"]

        # construir conteúdo do card dinamicamente conforme visible_fields
        rows = []

        # primeira linha: mostrar VPCR e, se presente, o badge de Status
        vpcr_text = item.get("vpcr", item.get("VPCR", ""))
        first_row_controls = [
            ft.Text(vpcr_text, size=base_font + 2, weight=ft.FontWeight.BOLD, color=colors["text_container_primary"], expand=True)
        ]
        if "Status" in self.visible_fields:
            first_row_controls.append(
                ft.Container(
                    content=ft.Text(status_val, size=base_font, color=ft.Colors.WHITE),
                    bgcolor=status_color,
                    padding=ft.padding.symmetric(horizontal=8, vertical=2),
                    border_radius=10
                )
            )

        rows.append(ft.Row(first_row_controls, alignment=ft.MainAxisAlignment.SPACE_BETWEEN))

        # Adicionar linha "Title:" abaixo do título se Title estiver nos campos visíveis
        if "Title" in self.visible_fields:
            title_text = item.get("Title", "")
            rows.append(ft.Row([ft.Text("Title:", size=base_font, weight=ft.FontWeight.BOLD, color=colors["text_container_primary"]), ft.Text(title_text, size=base_font, color=colors["text_container_secondary"])], spacing=8))

        # outras fields (excluir Title já mostrado)
        for f in self.visible_fields:
            if f in ("Title", "Status"):
                continue
            val = item.get(f, "")
            if val != "":
                # Para campos que contém listas separadas por ;, formatá-las como lista
                if f in ["PNs", "Plants Affected", "Affected Items"] and ";" in str(val):
                    items_list = [item.strip() for item in str(val).split(";") if item.strip()]
                    if items_list:
                        formatted_val = "• " + "\n• ".join(items_list)
                    else:
                        formatted_val = str(val)
                else:
                    formatted_val = str(val)
                    
                rows.append(ft.Row([ft.Text(f + ":", size=base_font, weight=ft.FontWeight.BOLD, color=colors["text_container_primary"]), ft.Text(formatted_val, size=base_font, color=colors["text_container_secondary"])], spacing=8))

        # Adicionar linha com o ícone de notificação (antes de instanciar container principal)
        def handle_notification_click(e, current_item=item):
            # Abre o diálogo de TODOs para o item selecionado
            self.open_todo_dialog(current_item)

        # Verificar se existe TODOs para este item
        item_id = item.get("ID")
        has_incomplete = self.db_manager.has_incomplete_todos(item_id)
        
        # Definir cor do ícone baseado no status
        notification_color = ft.Colors.ORANGE if has_incomplete else colors["accent"]
        
        # Criar o IconButton com tamanho maior
        notification_button = ft.IconButton(
            ft.Icons.NOTIFICATIONS,
            icon_size=28,  # Aumentado para 28px
            icon_color=notification_color,
            on_click=handle_notification_click,
            tooltip="Gerenciar TODOs"
        )
        
        # Animar sempre que houver TODOs incompletos, independente do filtro
        if has_incomplete:
            # Se já está animando este item, não iniciar nova animação
            if item_id not in self.animated_icons:
                self.animated_icons[item_id] = notification_button
                # Iniciar animação em thread separada
                import threading
                animation_thread = threading.Thread(
                    target=self.start_icon_animation, 
                    args=(notification_button, item_id)
                )
                animation_thread.daemon = True
                animation_thread.start()
            else:
                # Se já estava animando, apenas atualizar a referência do botão
                self.animated_icons[item_id] = notification_button

        # Botão de salvar (fica à esquerda do sino). Cor muda se item estiver "sujo".
        item_id = item.get("ID")
        is_dirty = item_id in self.dirty_items
        save_color = (ft.Colors.ORANGE_400 if is_dirty else colors["accent"]) if hasattr(ft.Colors, 'ORANGE_400') else (colors["accent"])

        def handle_save_click(e, current_item=item):
            self.save_card_changes(current_item)

        save_button = ft.IconButton(
            icon=ft.Icons.SAVE,
            icon_size=24,
            icon_color=save_color,
            tooltip="Salvar alterações deste card",
            on_click=handle_save_click,
        )
        # Guardar referência para atualizações futuras de cor
        self.card_save_buttons[item_id] = save_button

        rows.append(
            ft.Row([
                ft.Container(expand=True),  # Espaço vazio expansível
                save_button,
                notification_button
            ], alignment=ft.MainAxisAlignment.END, spacing=8)
        )

        # Container principal do card (agora inclui a linha do sino)
        column = ft.Column(rows, spacing=6)

        # Se estivermos em modo de seleção, mostrar checkbox à esquerda
        if getattr(self, 'card_select_mode', False):
            item_id = item.get("ID")
            checked = item_id in self.card_selection
            checkbox = ft.Checkbox(value=checked, on_change=lambda e, iid=item_id: self._handle_card_checkbox_change(e, iid))
            # Colocar checkbox e conteúdo em uma linha para manter layout
            content = ft.Row([checkbox, ft.Container(width=8), column], alignment=ft.MainAxisAlignment.START)
        else:
            content = column

        card_container = ft.Container(
            content=content,
            padding=15,
            on_click=lambda e: self.select_item(item)
        )

        return ft.Card(
            content=card_container,
            color=card_bg_color,
            shadow_color=ft.Colors.BLACK26,
            elevation=2
        )
    
    def update_card_list(self, preserve_scroll=False):
        """Atualiza a lista de cards"""
        if hasattr(self, 'card_list'):
            # Salvar posição do scroll se solicitado
            scroll_position = None
            if preserve_scroll and hasattr(self.card_list, 'scroll_to'):
                try:
                    scroll_position = getattr(self.card_list, 'scroll_offset', None)
                except:
                    pass
            
            # Salvar animações ativas antes de limpar os cards
            active_animations = {}
            for item_id, btn in self.animated_icons.items():
                active_animations[item_id] = True
            
            self.card_list.controls.clear()
            for item in self.filtered_data:
                self.card_list.controls.append(self.create_card(item))
            
            # Restaurar animações para os cards recriados que devem continuar animando
            for item in self.filtered_data:
                item_id = item.get("ID")
                # Se este item tinha animação ativa anteriormente e tem TODOs incompletos
                if item_id in active_animations and self.db_manager.has_incomplete_todos(item_id):
                    # Reativar sua animação (será iniciada no create_card se necessário)
                    pass  # O create_card já fará isso automaticamente
                    
            self.card_list.update()
            
            # Restaurar posição do scroll se havia uma salva
            if scroll_position is not None:
                try:
                    self.card_list.scroll_to(offset=scroll_position)
                except:
                    pass

    def update_card_selection_only(self):
        """Atualiza apenas a aparência visual dos cards sem recriar a lista (preserva scroll)"""
        if hasattr(self, 'card_list'):
            # Iterar pelos cards existentes e atualizar apenas as cores
            for i, card_control in enumerate(self.card_list.controls):
                if i < len(self.filtered_data):
                    item = self.filtered_data[i]
                    item_id = item.get("ID")
                    
                    # Verificar se este card deveria estar selecionado
                    colors = self.theme_manager.get_theme_colors()
                    is_selected = self.selected_item_id == item_id
                    new_card_bg = colors["selected_card"] if is_selected else colors["card_bg"]
                    
                    # Atualizar a cor do card
                    if hasattr(card_control, 'color'):
                        card_control.color = new_card_bg
                        card_control.update()

    def _handle_card_checkbox_change(self, e, item_id):
        """Handler chamado quando um checkbox de card muda de estado"""
        try:
            if e.control.value:
                self.card_selection.add(item_id)
            else:
                if item_id in self.card_selection:
                    self.card_selection.remove(item_id)
        except Exception as ex:
            # Em caso de erro, tentar ler o valor do evento
            try:
                if getattr(e, 'data', None) in (True, 'true', 'True'):
                    self.card_selection.add(item_id)
                else:
                    if item_id in self.card_selection:
                        self.card_selection.remove(item_id)
            except Exception:
                pass
        # Atualizar contador no footer
        self._update_card_export_footer()

    def toggle_card_select_mode(self):
        """Ativa/desativa o modo de seleção de cards"""
        self.card_select_mode = not getattr(self, 'card_select_mode', False)
        # Sempre limpar seleção ao entrar/sair do modo (garantir estado limpo)
        self.card_selection.clear()
        # Atualizar footer visibilidade
        if hasattr(self, 'card_export_footer'):
            self.card_export_footer.visible = self.card_select_mode
        self._update_card_export_footer()
        # Recriar a lista para exibir/ocultar checkboxes
        self.update_card_list()

    def cancel_card_selection(self):
        """Cancela o modo de seleção e limpa seleção"""
        self.card_select_mode = False
        self.card_selection.clear()
        if hasattr(self, 'card_export_footer'):
            self.card_export_footer.visible = False
        self._update_card_export_footer()
        self.update_card_list()
        # Forçar atualização da página para garantir que os checkboxes sejam recriados
        if hasattr(self, 'page'):
            self.page.update()

    def show_custom_notification(self, message, color=ft.Colors.BLUE_400, duration=3000):
        """Cria uma notificação personalizada usando banner no topo"""
        print(f"=== MOSTRANDO NOTIFICAÇÃO: {message} ===")
        if hasattr(self, 'page') and self.page:
            try:
                # Limpar notificação anterior se existir
                self.hide_custom_notification()
                
                # Criar banner simples
                self.notification_banner = ft.Banner(
                    bgcolor=color,
                    content=ft.Text(message, color=ft.Colors.WHITE, weight=ft.FontWeight.BOLD),
                    actions=[
                        ft.TextButton("Fechar", style=ft.ButtonStyle(color=ft.Colors.WHITE), on_click=lambda e: self.hide_custom_notification())
                    ]
                )
                
                # Adicionar à página
                self.page.banner = self.notification_banner
                self.page.banner.open = True
                self.page.update()
                print("Banner de notificação criado")
                
                # Auto-remover após duração
                if duration > 0:
                    import threading
                    def auto_hide():
                        import time
                        time.sleep(duration / 1000.0)
                        self.hide_custom_notification()
                    threading.Thread(target=auto_hide).start()
                
            except Exception as e:
                print(f"Erro ao criar notificação: {e}")
                import traceback
                traceback.print_exc()

    def hide_custom_notification(self):
        """Remove a notificação personalizada"""
        try:
            if hasattr(self, 'page') and hasattr(self.page, 'banner') and self.page.banner:
                self.page.banner.open = False
                self.page.update()
                print("Banner de notificação removido")
        except Exception as e:
            print(f"Erro ao remover notificação: {e}")

    # Métodos de teste removidos (test_snackbar, test_dialog) — limpeza de código legado

    def _update_card_export_footer(self):
        """Atualiza o texto do footer com a contagem de itens selecionados"""
        if hasattr(self, 'card_export_count_text'):
            count = len(self.card_selection)
            self.card_export_count_text.value = f"{count} selecionado{'s' if count != 1 else ''}"
            try:
                self.card_export_count_text.update()
            except Exception:
                pass

    def export_selected_cards(self):
        """Exporta os cards selecionados para PDF com seletor de arquivo"""        
        if not self.card_selection:
            # mostrar mensagem
            if hasattr(self, 'page') and self.page:
                self.notify("⚠️ Nenhum card selecionado para exportar", kind="warn", auto_hide=3000)
            return

        # Abrir seletor de arquivo para PDF
        def on_pdf_save_result(e: ft.FilePickerResultEvent):
            if e.path:
                try:
                    # Reunir dados dos items selecionados NO MOMENTO do salvamento
                    selected_items = [item for item in self.filtered_data if item.get('ID') in self.card_selection]
                    if not selected_items:
                        # fallback: procurar em todos os dados
                        selected_items = [item for item in self.sample_data if item.get('ID') in self.card_selection]
                    
                    self._generate_pdf_report(selected_items, e.path)
                    # Notificar sucesso
                    if hasattr(self, 'page') and self.page:
                        filename = os.path.basename(e.path)
                        self.notify(f"✅ PDF exportado: {filename}", kind="success", auto_hide=4000)
                    # Sair do modo seleção
                    self.cancel_card_selection()
                    # Forçar atualização da interface
                    if hasattr(self, 'page'):
                        self.page.update()
                except Exception as ex:
                    import traceback
                    error_details = traceback.format_exc()
                    print(f"Erro detalhado ao gerar PDF: {error_details}")
                    
                    if hasattr(self, 'page') and self.page:
                        # Mensagem de erro detalhada para debug
                        error_msg = f"Erro ao gerar PDF: {str(ex)}"
                        if "reportlab" in str(ex).lower():
                            error_msg += "\n(Problema com biblioteca ReportLab no executável)"
                        elif "icon" in str(ex).lower() or "image" in str(ex).lower():
                            error_msg += "\n(Problema ao carregar ícone Cummins)"
                        elif "font" in str(ex).lower():
                            error_msg += "\n(Problema com fonte no executável)"
                        elif "path" in str(ex).lower() or "file" in str(ex).lower():
                            error_msg += "\n(Problema de caminho de arquivo)"
                        
                        self.notify(f"❌ {error_msg}", kind="error", auto_hide=6000)
                    else:
                        print("Page não está disponível para mostrar SnackBar")

        # Configurar e abrir seletor de arquivo
        if not hasattr(self, 'pdf_save_dialog'):
            self.pdf_save_dialog = ft.FilePicker(on_result=on_pdf_save_result)
            self.page.overlay.append(self.pdf_save_dialog)
            self.page.update()

        # Sugerir nome padrão
        import datetime
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        default_name = f"vpcr_export_{timestamp}.pdf"
        
        self.pdf_save_dialog.save_file(
            dialog_title="Salvar exportação PDF",
            file_name=default_name,
            file_type=ft.FilePickerFileType.CUSTOM,
            allowed_extensions=["pdf"]
        )

    def _generate_pdf_report(self, selected_items, file_path):
        """Gera o relatório PDF com os items selecionados"""
        try:
            from reportlab.lib.pagesizes import A4, landscape
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, Image, HRFlowable
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from reportlab.lib.units import mm, inch
            from reportlab.pdfbase import pdfmetrics
            from reportlab.pdfbase.ttfonts import TTFont
            from reportlab.graphics.shapes import Drawing, Rect
            from reportlab.platypus.flowables import HRFlowable
            import datetime
            import os
            import sys
        except ImportError as e:
            raise Exception(f"Erro ao importar bibliotecas ReportLab: {e}")
        except Exception as e:
            raise Exception(f"Erro geral ao carregar dependências: {e}")
        
        # Cores limpas e profissionais
        cummins_red = colors.Color(0.8, 0.1, 0.1)        # Vermelho Cummins
        light_gray = colors.Color(0.95, 0.95, 0.95)      # Cinza claro
        medium_gray = colors.Color(0.8, 0.8, 0.8)        # Cinza médio
        dark_gray = colors.Color(0.3, 0.3, 0.3)          # Cinza escuro
        
        # Configurar documento PDF em landscape para mais espaço
        doc = SimpleDocTemplate(
            file_path,
            pagesize=landscape(A4),
            rightMargin=15*mm,
            leftMargin=15*mm,
            topMargin=15*mm,
            bottomMargin=20*mm
        )
        
        # Estilos aprimorados
        styles = getSampleStyleSheet()
        
        # Título principal
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            spaceAfter=5,
            spaceBefore=0,
            textColor=cummins_red,
            alignment=1,  # Center
            fontName='Helvetica-Bold'
        )
        
        # Subtítulo
        subtitle_style = ParagraphStyle(
            'SubTitle',
            parent=styles['Normal'],
            fontSize=12,
            spaceAfter=20,
            textColor=dark_gray,
            alignment=1,  # Center
            fontName='Helvetica'
        )
        
        # Header de informações
        info_style = ParagraphStyle(
            'InfoStyle',
            parent=styles['Normal'],
            fontSize=11,
            spaceAfter=8,
            textColor=dark_gray,
            fontName='Helvetica',
            leftIndent=0
        )
        
        # Título do card
        card_title_style = ParagraphStyle(
            'CardTitle',
            parent=styles['Heading2'],
            fontSize=16,
            spaceAfter=8,
            spaceBefore=15,
            textColor=colors.white,
            fontName='Helvetica-Bold',
            leftIndent=8,
            rightIndent=8
        )
        
        # Campo label (negrito)
        field_label_style = ParagraphStyle(
            'FieldLabel',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=2,
            textColor=cummins_red,
            fontName='Helvetica-Bold'
        )
        
        # Campo valor
        field_value_style = ParagraphStyle(
            'FieldValue',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=2,
            textColor=colors.black,
            fontName='Helvetica'
        )
        
        # Conteúdo do PDF
        story = []
        
        # Header decorativo com logo da Cummins
        # Tentar carregar o ícone da Cummins
        cummins_logo = None
        try:
            # Verificar se estamos executando como executável PyInstaller
            if getattr(sys, 'frozen', False):
                # Executável PyInstaller
                logo_path = os.path.join(sys._MEIPASS, "cummins.ico")
            else:
                # Desenvolvimento normal
                logo_path = os.path.join(os.path.dirname(__file__), "cummins.ico")
            
            if os.path.exists(logo_path):
                cummins_logo = Image(logo_path, width=12*mm, height=12*mm)
                print(f"Logo Cummins carregado com sucesso de: {logo_path}")
            else:
                print(f"Arquivo de logo não encontrado em: {logo_path}")
                
        except Exception as e:
            print(f"Erro ao carregar logo da Cummins: {e}")
            # Re-raise para que seja capturado pelo tratamento principal
            if "cannot identify image file" in str(e):
                raise Exception(f"Arquivo de imagem Cummins corrompido ou inválido: {e}")
            elif "No such file" in str(e):
                raise Exception(f"Ícone Cummins não encontrado no executável: {e}")
            else:
                raise Exception(f"Erro desconhecido ao carregar ícone Cummins: {e}")
        
        # Criar conteúdo da célula vermelha: texto à esquerda e logo à direita
        if cummins_logo:
            # Tabela interna para texto + logo na mesma célula
            logo_text_table = Table([['RELATÓRIO VPCR', cummins_logo]], colWidths=[170*mm, 30*mm])
            logo_text_table.setStyle(TableStyle([
                ('ALIGN', (0, 0), (0, 0), 'LEFT'),
                ('ALIGN', (1, 0), (1, 0), 'CENTER'),
                ('VALIGN', (0, 0), (1, 0), 'MIDDLE'),
                ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (0, 0), 20),
                ('TEXTCOLOR', (0, 0), (0, 0), colors.white),
                ('LEFTPADDING', (0, 0), (0, 0), 10),
                ('RIGHTPADDING', (1, 0), (1, 0), 5),
                ('TOPPADDING', (1, 0), (1, 0), 5),
                ('BOTTOMPADDING', (1, 0), (1, 0), 5),
            ]))
            header_content = logo_text_table
        else:
            header_content = 'RELATÓRIO VPCR'
        
        header_table = Table([
            ['', header_content, '']
        ], colWidths=[50*mm, 200*mm, 50*mm])
        
        def safe_apply_style(table_obj, style_cmds, context_desc=""):
            """Aplica TableStyle ignorando comandos potencialmente incompatíveis no executável.
            Se 'ROUNDEDCORNERS' causar erro (algumas versões do reportlab + build PyInstaller), remove e tenta novamente.
            """
            try:
                table_obj.setStyle(TableStyle(style_cmds))
            except Exception as ex:
                msg = str(ex).lower()
                if 'round' in msg and 'corner' in msg:
                    # Filtrar comandos ROUNDEDCORNERS e tentar novamente
                    filtered = [c for c in style_cmds if not (isinstance(c, tuple) and c and c[0] == 'ROUNDEDCORNERS')]
                    try:
                        table_obj.setStyle(TableStyle(filtered))
                        print(f"[PDF] Removido ROUNDEDCORNERS em '{context_desc}' devido a incompatibilidade no executável.")
                    except Exception as ex2:
                        print(f"[PDF] Falha ao aplicar estilo filtrado em '{context_desc}': {ex2}")
                else:
                    print(f"[PDF] Erro ao aplicar estilo em '{context_desc}': {ex}")

        safe_apply_style(header_table, [
            ('BACKGROUND', (1, 0), (1, 0), cummins_red),
            ('TEXTCOLOR', (1, 0), (1, 0), colors.white),
            ('ALIGN', (1, 0), (1, 0), 'LEFT'),
            ('VALIGN', (1, 0), (1, 0), 'MIDDLE'),
            ('FONTNAME', (1, 0), (1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (1, 0), (1, 0), 20),
            ('BOTTOMPADDING', (1, 0), (1, 0), 15),
            ('TOPPADDING', (1, 0), (1, 0), 15),
            ('LEFTPADDING', (1, 0), (1, 0), 15),
            ('ROUNDEDCORNERS', [5, 5, 5, 5]),
        ], context_desc="header_table")
        
        story.append(header_table)
        story.append(Spacer(1, 15))
        
        # Linha divisória elegante
        story.append(HRFlowable(width="100%", thickness=1, color=medium_gray))
        story.append(Spacer(1, 15))
        
        # Informações do relatório em caixas
        info_data = [
            ['Data de Geração:', datetime.datetime.now().strftime('%d/%m/%Y às %H:%M')],
            ['Total de Cards:', str(len(selected_items))],
            ['Usuário:', 'VPCR System']
        ]
        
        info_table = Table(info_data, colWidths=[60*mm, 80*mm])
        info_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), light_gray),
            ('TEXTCOLOR', (0, 0), (0, -1), cummins_red),
            ('TEXTCOLOR', (1, 0), (1, -1), colors.black),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('GRID', (0, 0), (-1, -1), 1, colors.white),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))
        
        story.append(info_table)
        story.append(Spacer(1, 25))
        
        # Processar cada card
        for i, item in enumerate(selected_items, 1):
            # Adicionar separador antes de cada card (exceto o primeiro) para garantir espaço visível
            if i > 1:
                # Espaço superior antes da linha
                story.append(Spacer(1, 18))
                # Linha divisória
                story.append(HRFlowable(width="100%", thickness=1, color=medium_gray))
                # Espaço após a linha
                story.append(Spacer(1, 18))
            # Card container com título
            card_elements = []
            
            # Header do card
            card_title = f"{item.get('Title', 'Untitled')}"
            
            # Título do card com background colorido
            title_table = Table([[card_title]], colWidths=[260*mm])
            safe_apply_style(title_table, [
                ('BACKGROUND', (0, 0), (-1, -1), cummins_red),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.white),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 14),
                ('LEFTPADDING', (0, 0), (-1, -1), 15),
                ('RIGHTPADDING', (0, 0), (-1, -1), 15),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 9),
                ('ROUNDEDCORNERS', [8, 8, 0, 0]),
            ], context_desc="title_table")
            card_elements.append(title_table)
            
            # Sem espaçamento para conectar diretamente com o status
            
            # Criar linha de status visual como na imagem
            # Definir os status do workflow exatamente como na interface
            workflow_steps = [
                "Draft", "Preliminary Change Manager Review", "Preliminary Review",
                "Cross Functional Review", "Secondary Change Manager Review", 
                "Pending Resource Assignment", "Cost and Lead Time Analysis",
                "Engineering Work in Progress", "Purchasing Work in Progress",
                "Pending Plant Implementation", "Work Complete"
            ]
            
            # Criar status visual como uma linha mesclada (estilo Excel)
            status_cells = []
            for i, step in enumerate(workflow_steps):
                is_completed = i <= 2  # Primeiros 3 completos
                
                if is_completed:
                    # Ícone + texto em uma célula
                    status_content = f"✓\n{step}"
                    color = colors.Color(0, 0.6, 0)  # Verde
                else:
                    # Ícone + texto em uma célula  
                    status_content = f"○\n{step}"
                    color = colors.Color(0.5, 0.5, 0.5)  # Cinza
                
                status_cells.append(Paragraph(status_content, ParagraphStyle(
                    'StatusCell',
                    fontSize=7,
                    alignment=1,  # Centro
                    textColor=color,
                    leading=8
                )))
            
            # Criar tabela com uma única linha (como linha mesclada do Excel)
            # Largura total igual à tabela principal: 260mm dividido em 11 colunas
            workflow_visual_table = Table([status_cells], 
                                        colWidths=[260*mm / 11] * 11,
                                        rowHeights=[15*mm])
            safe_apply_style(workflow_visual_table, [
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ('TOPPADDING', (0, 0), (-1, -1), 0),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 0),
                ('LEFTPADDING', (0, 0), (-1, -1), 1),
                ('RIGHTPADDING', (0, 0), (-1, -1), 1),
                ('BACKGROUND', (0, 0), (-1, -1), colors.white),
                ('LINEABOVE', (0, 0), (-1, 0), 1, medium_gray),
                ('LINEBEFORE', (0, 0), (0, -1), 1, medium_gray),
                ('LINEAFTER', (-1, 0), (-1, -1), 1, medium_gray),
            ], context_desc="workflow_visual_table")
            
            # Adicionar a linha de status visual ao card
            card_elements.append(workflow_visual_table)
            
            # Lista completa de todos os campos incluindo novos
            all_fields = [
                ("Title", item.get("Title", "")),
                ("ID", item.get("ID", "")),
                ("Status", item.get("Status", "")),
                ("Category", item.get("Category", "")),
                ("Initiated Date", item.get("Initiated Date", "")),
                ("Last Update", item.get("Last Update", "")),
                ("Closed Date", item.get("Closed Date", "")),
                ("Supplier", item.get("Supplier", "")),
                ("Part Numbers", item.get("PNs", "")),
                ("Plants Affected", item.get("Plants Affected", "")),
                ("Requestor", item.get("Requestor", "")),
                ("Sourcing Manager", item.get("Sourcing Manager", "") or item.get("Sourcing", "")),
                ("SQIE", item.get("SQIE", "")),
                ("Continuity", item.get("Continuity", "")),
                ("RFQ", item.get("RFQ", "")), ("DRA", item.get("DRA", "")),
                ("DQR", item.get("DQR", "")), ("LOI", item.get("LOI", "")),
                ("Tooling", item.get("Tooling", "")), ("Drawing", item.get("Drawing", "")),
                ("PO Alfa", item.get("PO Alfa", "")), ("SR", item.get("SR", "")),
                ("Deviation", item.get("Deviation", "")), ("PO Beta", item.get("PO Beta", "")),
                ("PPAP", item.get("PPAP", "")), ("GBPA", item.get("GBPA", "")),
                ("EDI", item.get("EDI", "")), ("SCR", item.get("SCR", "")),
                ("Comments", item.get("Comments", "")),
                ("Link", item.get("Link", "")),
                ("Log", item.get("Log", ""))
            ]
            
            # Filtrar apenas campos com conteúdo
            filled_fields = [(label, str(value)) for label, value in all_fields if value and str(value).strip()]
            
            # Organizar campos em duas colunas por linha
            section_data = []
            for j in range(0, len(filled_fields), 2):
                row = []
                
                # Primeira coluna
                if j < len(filled_fields):
                    label1, value1 = filled_fields[j]
                    row.extend([
                        Paragraph(f"<b>{label1}:</b>", field_label_style),
                        Paragraph(str(value1), field_value_style)
                    ])
                else:
                    row.extend(['', ''])
                
                # Segunda coluna
                if j + 1 < len(filled_fields):
                    label2, value2 = filled_fields[j + 1]
                    row.extend([
                        Paragraph(f"<b>{label2}:</b>", field_label_style),
                        Paragraph(str(value2), field_value_style)
                    ])
                else:
                    row.extend(['', ''])
                
                section_data.append(row)
            
            if section_data:
                # Remover última linha vazia
                if section_data and all(cell == '' for cell in section_data[-1]):
                    section_data.pop()
                
                # Tabela principal do card
                main_table = Table(section_data, colWidths=[60*mm, 70*mm, 60*mm, 70*mm])
                safe_apply_style(main_table, [
                    ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, light_gray] * 50),
                    ('GRID', (0, 0), (-1, -1), 0.5, medium_gray),
                    ('LINEBEFORE', (0, 0), (0, -1), 1, medium_gray),
                    ('LINEAFTER', (-1, 0), (-1, -1), 1, medium_gray),
                    ('LINEBELOW', (0, -1), (-1, -1), 1, medium_gray),
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('LEFTPADDING', (0, 0), (-1, -1), 8),
                    ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                    ('TOPPADDING', (0, 0), (-1, -1), 4),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ('ROUNDEDCORNERS', [0, 0, 8, 8]),
                ], context_desc="main_table")
                

                
                card_elements.append(main_table)
            
            # Adicionar card completo como um grupo (mantém título, workflow e tabela juntos)
            story.append(KeepTogether(card_elements))
        
        # Gerar PDF com tratamento de erro robusto
        try:
            doc.build(story)
            print(f"PDF gerado com sucesso: {file_path}")
        except Exception as e:
            print(f"Erro ao construir PDF: {e}")
            if "Permission denied" in str(e):
                raise Exception(f"Permissão negada para salvar PDF. Verifique se o arquivo não está aberto em outro programa: {e}")
            elif "No space left" in str(e):
                raise Exception(f"Espaço insuficiente no disco para salvar o PDF: {e}")
            elif "reportlab" in str(e).lower():
                if "round" in str(e).lower() and "corner" in str(e).lower():
                    raise Exception(
                        "Incompatibilidade com 'ROUNDEDCORNERS' no ReportLab dentro do executável. O código já tenta remover automaticamente. Rebuild sugerido com: "
                        "--collect-data reportlab --collect-submodules reportlab. Detalhe: " + str(e)
                    )
                raise Exception(f"Erro interno da biblioteca ReportLab no executável: {e}. Sugestão: incluir '--collect-data reportlab --collect-submodules reportlab' no PyInstaller e testar em Python 3.12 se persistir.")
            elif "font" in str(e).lower():
                raise Exception(f"Erro com fonte no executável. Verifique se as fontes estão disponíveis: {e}")
            else:
                raise Exception(f"Erro desconhecido ao gerar PDF: {e}")

    def open_todo_dialog(self, item):
        """Abre o diálogo de gerenciamento de TODOs para um item"""
        if not item:
            # Item inválido, nada a fazer
            return
        
        colors = self.theme_manager.get_theme_colors()
        item_id = item.get("ID") or item.get("id")
        
        if item_id is None:
            return
        
        try:
            # Lista temporária para armazenar TODOs durante a edição
            self.temp_todos = []
            
            # Carregar TODOs existentes do banco
            existing_todos = self.db_manager.get_todos_for_item(item_id)
            for todo in existing_todos:
                self.temp_todos.append({
                    'id': todo['id'],
                    'description': todo['description'], 
                    'completed': todo['completed'],
                    'is_existing': True
                })
            
            # Se não há TODOs, adicionar um campo vazio
            if not self.temp_todos:
                self.temp_todos.append({
                    'id': None,
                    'description': '',
                    'completed': False,
                    'is_existing': False
                })
            
            def create_todo_row(todo_data, index):
                """Cria uma linha de TODO com checkbox e campo de texto"""
                def on_checkbox_change(e):
                    self.temp_todos[index]['completed'] = e.control.value
                
                def on_text_change(e):
                    self.temp_todos[index]['description'] = e.control.value
                
                def delete_todo_row(e):
                    if len(self.temp_todos) > 1:
                        self.temp_todos.pop(index)
                        self.refresh_todo_dialog(item, item_id, colors)
                
                return ft.Row([
                    ft.Checkbox(
                        value=todo_data['completed'],
                        on_change=on_checkbox_change
                    ),
                    ft.TextField(
                        value=todo_data['description'],
                        hint_text="Digite a descrição do TODO...",
                        multiline=True,
                        min_lines=1,
                        max_lines=3,
                        filled=True,
                        bgcolor=colors["field_bg"],
                        color=colors["field_text"],
                        border_color=colors["field_border"],
                        on_change=on_text_change,
                        expand=True
                    ),
                    ft.IconButton(
                        ft.Icons.DELETE,
                        icon_color=ft.Colors.RED,
                        icon_size=20,
                        on_click=delete_todo_row,
                        disabled=len(self.temp_todos) <= 1
                    )
                ], alignment=ft.MainAxisAlignment.START, spacing=8)
            
            def add_new_todo(e):
                """Adiciona uma nova linha de TODO"""
                self.temp_todos.append({
                    'id': None,
                    'description': '',
                    'completed': False,
                    'is_existing': False
                })
                self.refresh_todo_dialog(item, item_id, colors)
            
            def save_and_close(e):
                """Salva todos os TODOs no banco e fecha o diálogo"""
                try:
                    # Primeiro, excluir TODOs que foram removidos
                    existing_ids = {todo['id'] for todo in existing_todos if todo['id']}
                    temp_ids = {todo['id'] for todo in self.temp_todos if todo['id'] and todo['is_existing']}
                    
                    # IDs que foram removidos
                    removed_ids = existing_ids - temp_ids
                    for todo_id in removed_ids:
                        self.db_manager.delete_todo(todo_id)
                    
                    # Salvar/atualizar TODOs
                    for todo_data in self.temp_todos:
                        description = todo_data['description'].strip()
                        if description:  # Só salvar se tem descrição
                            if todo_data['is_existing'] and todo_data['id']:
                                # Atualizar TODO existente
                                self.db_manager.update_todo(
                                    todo_data['id'],
                                    description=description,
                                    completed=todo_data['completed']
                                )
                            else:
                                # Criar novo TODO
                                new_id = self.db_manager.add_todo(item_id, description)
                                if todo_data['completed']:
                                    # Se já está marcado como completo, atualizar
                                    self.db_manager.update_todo(new_id, completed=True)
                    
                    self.close_todo_dialog()
                    # TODOs salvos
                    
                except Exception as ex:
                    print(f"Erro ao salvar TODOs: {ex}")
            
            self.refresh_todo_dialog(item, item_id, colors, save_and_close, add_new_todo)
            
        except Exception as ex:
            import traceback
            print("ERRO em open_todo_dialog:", ex)
            traceback.print_exc()
    
    def refresh_todo_dialog(self, item, item_id, colors, save_and_close=None, add_new_todo=None):
        """Atualiza o conteúdo do diálogo de TODOs"""
        
        # Função para adicionar um novo TODO
        def add_new_todo_handler(e):
            self.temp_todos.append({
                'id': None,
                'description': '',
                'completed': False,
                'is_existing': False
            })
            self.refresh_todo_dialog(item, item_id, colors)
        
        # Função para salvar e fechar
        def save_and_close_handler(e):
            try:
                # Carregar TODOs existentes do banco para comparação
                existing_todos = self.db_manager.get_todos_for_item(item_id)
                existing_ids = {todo['id'] for todo in existing_todos}
                temp_ids = {todo['id'] for todo in self.temp_todos if todo['id'] and todo['is_existing']}
                
                # Deletar TODOs removidos
                removed_ids = existing_ids - temp_ids
                for todo_id in removed_ids:
                    self.db_manager.delete_todo(todo_id)
                
                # Salvar/atualizar TODOs
                for todo_data in self.temp_todos:
                    description = todo_data['description'].strip()
                    if description:  # Só salvar se tem descrição
                        if todo_data['is_existing'] and todo_data['id']:
                            # Atualizar TODO existente
                            self.db_manager.update_todo(
                                todo_data['id'],
                                description=description,
                                completed=todo_data['completed']
                            )
                        else:
                            # Criar novo TODO
                            new_id = self.db_manager.add_todo(item_id, description)
                            if todo_data['completed']:
                                self.db_manager.update_todo(new_id, completed=True)
                
                self.close_todo_dialog()
                # Atualizar animações dos ícones após salvar
                self.update_icon_animations()
                
            except Exception as ex:
                print(f"Erro ao salvar TODOs: {ex}")
                import traceback
                traceback.print_exc()
        
        # Criar linhas de TODOs
        todo_rows = []
        
        for i, todo_data in enumerate(self.temp_todos):
            # Criar campos para este TODO
            checkbox = ft.Checkbox(value=todo_data['completed'])
            textfield = ft.TextField(
                value=todo_data['description'],
                hint_text="Digite a descrição do TODO...",
                multiline=True,
                min_lines=1,
                max_lines=3,
                expand=True
            )
            delete_btn = ft.IconButton(
                ft.Icons.DELETE,
                icon_color=ft.Colors.RED,
                disabled=len(self.temp_todos) <= 1
            )
            
            # Definir handlers com closure correto
            def make_checkbox_handler(index):
                def handler(e):
                    self.temp_todos[index]['completed'] = e.control.value
                return handler
            
            def make_textfield_handler(index):
                def handler(e):
                    self.temp_todos[index]['description'] = e.control.value
                return handler
            
            def make_delete_handler(index):
                def handler(e):
                    if len(self.temp_todos) > 1:
                        self.temp_todos.pop(index)
                        self.refresh_todo_dialog(item, item_id, colors)
                return handler
            
            checkbox.on_change = make_checkbox_handler(i)
            textfield.on_change = make_textfield_handler(i)
            delete_btn.on_click = make_delete_handler(i)
            
            todo_row = ft.Row([
                checkbox,
                textfield,
                delete_btn
            ], alignment=ft.MainAxisAlignment.START, spacing=8)
            
            todo_rows.append(todo_row)
        
        # Área de scroll com os TODOs
        scroll_area = ft.Column(
            todo_rows,
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
            height=300
        )
        
        # Botão de adicionar TODO
        add_button = ft.ElevatedButton(
            text="+ Adicionar TODO",
            icon=ft.Icons.ADD,
            on_click=add_new_todo_handler
        )
        
        # Conteúdo principal
        # Definiremos a cor de fundo uniforme (igual ao diálogo)
        uniform_bg = colors.get("secondary", colors.get("surface", "#2d2d2d"))

        content_column = ft.Column([
            ft.Text(
                f"TODOs para: {item.get('Title', 'Item')}",
                size=16,
                weight=ft.FontWeight.BOLD,
                color=colors.get("text_container_primary", ft.Colors.WHITE)
            ),
            ft.Container(
                content=scroll_area,
                bgcolor=uniform_bg,
                padding=10,
                border_radius=8
            ),
            ft.Row([add_button], alignment=ft.MainAxisAlignment.CENTER),
        ], spacing=16)
        
        # Botões de ação
        action_buttons = [
            ft.TextButton("Fechar", on_click=lambda e: self.close_todo_dialog()),
            ft.ElevatedButton("Salvar", on_click=save_and_close_handler)
        ]
        
        # Criar diálogo (aplicar cores do tema)
        dialog_bg = colors.get("secondary", "#2d2d2d")
        surface_bg = colors.get("surface", dialog_bg)

        # Ajustar o container principal de conteúdo para refletir o tema
        themed_content_container = ft.Container(
            content=content_column,
            width=600,
            height=450,
            bgcolor=dialog_bg,
            padding=12,
            border_radius=10
        )

        self.todo_dialog = ft.AlertDialog(
            modal=True,
            title=ft.Text(
                f"Gerenciar TODOs - {item.get('Title', 'Item')}",
                size=18,
                weight=ft.FontWeight.BOLD,
                color=colors.get("text_container_primary", ft.Colors.WHITE)
            ),
            content=themed_content_container,
            actions=action_buttons,
            actions_alignment=ft.MainAxisAlignment.END
        )

        # Tentar definir bgcolor diretamente (nem sempre disponível em todas versões)
        try:
            self.todo_dialog.bgcolor = dialog_bg
        except Exception:
            pass
        
        try:
            self.page.open(self.todo_dialog)
        except Exception as e:
            print(f"Erro ao abrir diálogo: {e}")
            import traceback
            traceback.print_exc()

    def handle_toggle_and_refresh(self, todo_id, item):
        self.db_manager.toggle_todo(todo_id)
        # Recarrega diálogo mantendo aberto
        self.open_todo_dialog(item)

    def close_todo_dialog(self):
        """Fecha o diálogo de TODOs"""
        try:
            if hasattr(self, 'todo_dialog') and self.todo_dialog:
                self.page.close(self.todo_dialog)
        except Exception as e:
            # Fallback method
            if self.page.dialog:
                self.page.dialog.open = False
                self.page.update()

    def populate_filter_options(self):
        """Popula as opções dos filtros com chips de multiseleção"""
        # coletar valores únicos de todos os dados
        vpcr_vals = sorted({item.get("vpcr", "") for item in self.sample_data if item.get("vpcr", "")})
        sourcing_vals = sorted({item.get("Sourcing Manager", "") for item in self.sample_data if item.get("Sourcing Manager", "")})
        status_vals = sorted({item.get("Status", "") for item in self.sample_data if item.get("Status", "")})
        supplier_vals = sorted({item.get("Supplier", "") for item in self.sample_data if item.get("Supplier", "")})
        requestor_vals = sorted({item.get("Requestor", "") for item in self.sample_data if item.get("Requestor", "")})
        continuity_vals = sorted({item.get("Continuity", "") for item in self.sample_data if item.get("Continuity", "")})

        colors = self.theme_manager.get_theme_colors()

        # armazenar valores para uso posterior
        self.filter_options = {
            "VPCR": vpcr_vals,
            "Sourcing Manager": sourcing_vals,
            "Status": status_vals,
            "Supplier": supplier_vals,
            "Requestor": requestor_vals,
            "Continuity": continuity_vals
        }

        colors = self.theme_manager.get_theme_colors()

        def create_clickable_filter(field_name, container):
            def show_dropdown(e):
                self.show_dropdown_panel(field_name)

            container.content = ft.Row([
                ft.Text(field_name, size=12, color=colors["field_text"], expand=True),
                ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=16, color=colors["field_text"])
            ])
            container.on_click = show_dropdown

        # criar containers clicáveis para cada filtro
        create_clickable_filter("VPCR", self.filter_vpcr_chips)
        create_clickable_filter("Sourcing Manager", self.filter_sourcing_manager_chips)
        create_clickable_filter("Status", self.filter_status_chips)
        create_clickable_filter("Supplier", self.filter_supplier_chips)
        create_clickable_filter("Requestor", self.filter_requestor_chips)
        create_clickable_filter("Continuity", self.filter_continuity_chips)
        
        # atualizar controles se já estiverem na página
        try:
            self.filter_vpcr_chips.update()
            self.filter_sourcing_manager_chips.update()
            self.filter_status_chips.update()
            self.filter_supplier_chips.update()
            self.filter_requestor_chips.update()
            self.filter_continuity_chips.update()
        except:
            pass
    
    def get_available_filter_options(self, exclude_field=None):
        """Calcula opções de filtro disponíveis baseadas nos filtros já aplicados"""
        # Aplicar todos os filtros EXCETO o campo especificado
        filtered_data = []
        for item in self.sample_data:
            include_item = True
            
            # Aplicar cada filtro se não for o campo excluído
            for field_name in ["VPCR", "Sourcing Manager", "Status", "Supplier", "Requestor", "Continuity"]:
                if field_name == exclude_field:
                    continue
                    
                selected_values = self.filter_selections.get(field_name, set())
                if selected_values:  # Se há valores selecionados, verificar se o item corresponde
                    item_value = item.get(field_name if field_name != "VPCR" else "vpcr", "")
                    if item_value not in selected_values:
                        include_item = False
                        break
            
            # Aplicar filtro de TODOs se ativo
            if include_item and self.show_only_active_todos:
                item_id = item.get("ID")
                has_incomplete_todos = self.db_manager.has_incomplete_todos(item_id)
                if not has_incomplete_todos:
                    include_item = False
            
            if include_item:
                filtered_data.append(item)
        
        # Calcular valores únicos disponíveis nos dados filtrados
        available_options = {
            "VPCR": sorted({item.get("vpcr", "") for item in filtered_data if item.get("vpcr", "")}),
            "Sourcing Manager": sorted({item.get("Sourcing Manager", "") for item in filtered_data if item.get("Sourcing Manager", "")}),
            "Status": sorted({item.get("Status", "") for item in filtered_data if item.get("Status", "")}),
            "Supplier": sorted({item.get("Supplier", "") for item in filtered_data if item.get("Supplier", "")}),
            "Requestor": sorted({item.get("Requestor", "") for item in filtered_data if item.get("Requestor", "")}),
            "Continuity": sorted({item.get("Continuity", "") for item in filtered_data if item.get("Continuity", "")})
        }
        
        return available_options

    def show_dropdown_panel(self, field_name: str):
        """Mostra um painel dropdown customizado abaixo do filtro clicado (com busca e checkboxes)."""
        colors = self.theme_manager.get_theme_colors()
        # Usar opções disponíveis baseadas nos filtros já aplicados
        available_options = self.get_available_filter_options(exclude_field=field_name)
        values = available_options.get(field_name, [])

        # Criar checkboxes com estado atual
        checkboxes = []
        for value in values:
            checkboxes.append(
                ft.Checkbox(
                    label=value,
                    value=(value in self.filter_selections[field_name]),
                    label_style=ft.TextStyle(size=14, color=colors["text_primary"])
                )
            )

        # Funções de utilidade
        def apply_search_filter(term: str):
            term = (term or "").strip().lower()
            for cb in checkboxes:
                cb.visible = (term in cb.label.lower()) if term else True
                cb.update()

        def select_all(e):
            for cb in checkboxes:
                if cb.visible:
                    cb.value = True
                    cb.update()

        def deselect_all(e):
            for cb in checkboxes:
                if cb.visible:
                    cb.value = False
                    cb.update()

        def clear_all(e):
            self.filter_selections[field_name].clear()
            for cb in checkboxes:
                cb.value = False
                cb.update()

        def apply_and_close(e):
            self.filter_selections[field_name] = {cb.label for cb in checkboxes if cb.value}
            self.update_filter_display(field_name)
            self.filter_data()
            self.hide_dropdown_panel()

        def cancel_and_close(e):
            self.hide_dropdown_panel()

        # Construir painel com largura máxima de 400px
        panel = ft.Container(
            bgcolor=colors["secondary"],
            border=ft.border.all(1, colors["field_border"]),
            border_radius=8,
            padding=10,
            width=400,  # Largura máxima de 400px
            content=ft.Column([
                ft.Row([
                    ft.IconButton(icon=ft.Icons.CLEAR_ALL, tooltip="Limpar tudo", on_click=clear_all),
                    ft.IconButton(icon=ft.Icons.SELECT_ALL, tooltip="Selecionar todos", on_click=select_all),
                    ft.IconButton(icon=ft.Icons.CHECK_BOX_OUTLINE_BLANK, tooltip="Desmarcar todos", on_click=deselect_all),
                ], spacing=4, alignment=ft.MainAxisAlignment.START),
                ft.TextField(
                    label="Buscar...",
                    on_change=lambda e: apply_search_filter(e.control.value),
                    autofocus=True,
                    expand=True  # Expandir para ocupar toda a largura disponível
                ),
                ft.Container(
                    content=ft.Column(checkboxes, tight=True, scroll=ft.ScrollMode.AUTO),
                    height=260,
                    expand=True  # Expandir para ocupar toda a largura disponível
                ),
                ft.Row([
                    ft.TextButton("Cancelar", on_click=cancel_and_close),
                    ft.ElevatedButton("Aplicar", on_click=apply_and_close)
                ], alignment=ft.MainAxisAlignment.END)
            ], spacing=10)
        )

        # Posicionamento: centralizar o painel na janela ou alinhar à esquerda com margem
        # Calcular coordenadas absolutas para posicionar a janela suspensa
        filter_top_position = 110  # Valor ajustado para posicionar abaixo dos filtros
        
        # Configurar o contêiner do painel para posicionamento absoluto no overlay
        self.dropdown_panel_container.left = 30  # margem fixa da esquerda
        self.dropdown_panel_container.top = filter_top_position
        self.dropdown_panel_container.content = panel
        self.dropdown_panel_container.visible = True
        self.dropdown_open_for = field_name
        self.page.update()

    def hide_dropdown_panel(self):
        self.dropdown_panel_container.visible = False
        self.dropdown_open_for = None
        self.page.update()

    def clear_all_filters(self, e=None):
        # limpar todas as seleções de todos os filtros
        for key in self.filter_selections.keys():
            self.filter_selections[key].clear()
            self.update_filter_display(key)
        
        # Reset do switch de TODOs ativos
        self.show_only_active_todos = False
        self.todos_filter_switch.value = False
        
        self.filter_data()

    def update_filter_display(self, field_name):
        """Atualiza o display do filtro com base nas seleções"""
        colors = self.theme_manager.get_theme_colors()
        selected = self.filter_selections[field_name]
        
        # encontrar o container correto
        container_map = {
            "VPCR": self.filter_vpcr_chips,
            "Sourcing Manager": self.filter_sourcing_manager_chips,
            "Status": self.filter_status_chips,
            "Supplier": self.filter_supplier_chips,
            "Requestor": self.filter_requestor_chips,
            "Continuity": self.filter_continuity_chips
        }
        container = container_map.get(field_name)
        
        if container and container.content and len(container.content.controls) > 0:
            # Sempre mostrar apenas o nome do campo, nunca os valores selecionados
            text = field_name
            
            # Criar nova estrutura com texto + badge (se houver seleções) + ícone dropdown
            controls = [
                ft.Text(text, size=12, color=colors["field_text"], expand=True)
            ]
            
            # Adicionar badge com número se houver qualquer seleção (1 ou mais)
            if selected and len(selected) > 0:
                controls.append(
                    ft.Container(
                        content=ft.Text(
                            str(len(selected)), 
                            size=10, 
                            color=ft.Colors.WHITE, 
                            weight=ft.FontWeight.BOLD
                        ),
                        bgcolor=colors["accent"],
                        width=20,
                        height=20,
                        border_radius=10,
                        alignment=ft.alignment.center,
                        margin=ft.margin.only(right=4)
                    )
                )
            
            # Ícone dropdown
            controls.append(
                ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=16, color=colors["field_text"])
            )
            
            # Atualizar o container
            container.content = ft.Row(controls, alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            container.update()

    def close_dialog(self, dlg):
        dlg.open = False
        self.page.update()

    def select_item(self, item):
        """Atualiza os campos detalhados com base no item selecionado"""
        self.selected_item = item
        self.selected_item_id = item.get("ID")
        
        # Mapear dados do item para detail_fields
        self.detail_fields.update({
            # VPCR Overview
            "Title": item.get("Title", ""),
            "Initiated Date": item.get("Initiated Date", "N/A"),
            "Last Update": item.get("Last Update", "N/A"),
            "Closed Date": item.get("Closed Date", ""),
            "Category": item.get("Category", "N/A"),
            "Supplier": item.get("Supplier", ""),
            "PNs": item.get("PNs", "N/A"),
            "Plants Affected": item.get("Plants Affected", "N/A"),
            # Request & Responsibility  
            "Requestor": item.get("Requestor", ""),
            "Sourcing": item.get("Sourcing Manager", ""),
            "SQIE": item.get("SQIE", "N/A"),
            "Continuity": item.get("Continuity", ""),
            # Documentation (campos genéricos)
            "RFQ": item.get("RFQ", "N/A"),
            "DRA": item.get("DRA", "N/A"),
            "DQR": item.get("DQR", "N/A"),
            "LOI": item.get("LOI", "N/A"),
            "Tooling": item.get("Tooling", "N/A"),
            "Drawing": item.get("Drawing", "N/A"),
            "PO Alfa": item.get("PO Alfa", ""),
            "SR": item.get("SR", ""),
            "Deviation": item.get("Deviation", ""),
            "PO Beta": item.get("PO Beta", ""),
            "PPAP": item.get("PPAP", ""),
            "GBPA": item.get("GBPA", ""),
            "EDI": item.get("EDI", ""),
            "SCR": item.get("SCR", ""),
            # L2 fields
            "Comments": item.get("Comments", ""),
            "Log": item.get("Log", f"Selecionado: {item.get('Title', 'Item')}")
        })
        
        # Atualizar a UI dos containers direitos se eles existirem
        self.update_detail_containers()
        
        # Atualizar apenas a aparência dos cards sem recriar a lista
        self.update_card_selection_only()

        # Garantir que painel direito mostre os detalhes agora
        try:
            if hasattr(self, 'right_panel') and hasattr(self, 'detail_main_content'):
                if self.right_panel.content is not self.detail_main_content:
                    self.right_panel.content = self.detail_main_content
                    self.right_panel.update()
        except Exception:
            pass

    def update_detail_containers(self):
        """Atualiza os containers de detalhes após seleção de item"""
        if hasattr(self, 'detail_overview') and hasattr(self, 'detail_request') and hasattr(self, 'detail_doc') and hasattr(self, 'detail_log'):
            # Atualizar overview
            self.update_overview_container()
            self.update_request_container()
            self.update_doc_container()
            self.update_l2_containers()
            self.page.update()

    def update_overview_container(self):
        """Atualiza container VPCR Overview"""
        colors = self.theme_manager.get_theme_colors()
        # Atualizar valores dos TextFields persistentes (criados no create_vpcr_tab)
        try:
            self.tf_title.value = self.detail_fields.get("Title", "")
            self.tf_title.update()
            self.tf_initiated.value = self.detail_fields.get("Initiated Date", "")
            self.tf_initiated.update()
            self.tf_last_update.value = self.detail_fields.get("Last Update", "")
            self.tf_last_update.update()
            self.tf_closed_date.value = self.detail_fields.get("Closed Date", "")
            self.tf_closed_date.update()
            self.tf_category.value = self.detail_fields.get("Category", "")
            self.tf_category.update()
            self.tf_supplier.value = self.detail_fields.get("Supplier", "")
            self.tf_supplier.update()
            self.tf_pns.value = self.detail_fields.get("PNs", "")
            self.tf_pns.update()
            self.tf_plants.value = self.detail_fields.get("Plants Affected", "")
            self.tf_plants.update()
            self.tf_link.value = self.detail_fields.get("Link", "")
            self.tf_link.update()
            self.tf_comments.value = self.detail_fields.get("Comments", "")
            self.tf_comments.update()
        except Exception:
            # Se algum campo não existir (inicialização), ignorar
            pass

    def update_request_container(self):
        """Atualiza container Request & Responsibility"""
        colors = self.theme_manager.get_theme_colors()
        # Atualizar TextFields persistentes se existirem
        try:
            self.tf_requestor.value = self.detail_fields.get("Requestor", "")
            self.tf_requestor.update()
            self.tf_sourcing.value = self.detail_fields.get("Sourcing", "")
            self.tf_sourcing.update()
            self.tf_sqie.value = self.detail_fields.get("SQIE", "")
            self.tf_sqie.update()
            self.tf_continuity.value = self.detail_fields.get("Continuity", "")
            self.tf_continuity.update()
        except Exception:
            pass

    def update_doc_container(self):
        """Atualiza container Documentation"""
        colors = self.theme_manager.get_theme_colors()
        
        # Dividir campos em grupos para minicards
        group1_fields = [("RFQ", False), ("DRA", False), ("DQR", False), ("LOI", False)]
        group2_fields = [("Tooling", False), ("Drawing", False), ("PO Alfa", False), ("SR", False)]
        group3_fields = [("Deviation", False), ("PO Beta", False), ("PPAP", False), ("GBPA", False)]
        group4_fields = [("EDI", False), ("SCR", False)]
        
        def create_doc_minicard(fields_list, title=""):
            rows = []
            for name, editable in fields_list:
                ctrl = ft.Row([
                    ft.Text(f"{name}:", size=10, color=colors["text_container_secondary"], expand=True), 
                    ft.Text(self.detail_fields.get(name, ""), size=10, color=colors["text_container_primary"], expand=2)
                ], spacing=4)
                rows.append(ctrl)
            
            content = ft.Column(rows, spacing=3)
            if title:
                content = ft.Column([
                    ft.Text(title, size=11, weight=ft.FontWeight.BOLD, color=colors["text_container_primary"]),
                    ft.Divider(height=1),
                    ft.Column(rows, spacing=3)
                ], spacing=2)
            
            return ft.Container(
                content=content,
                bgcolor=colors["surface"],
                padding=6,
                border_radius=6,
                margin=ft.margin.only(bottom=4)
            )
        
        # Atualizar campos dos TextFields de documentação se existirem
        try:
            for name, _ in group1_fields + group2_fields + group3_fields + group4_fields:
                if hasattr(self, 'tf_doc') and name in self.tf_doc:
                    self.tf_doc[name].value = self.detail_fields.get(name, "")
                    self.tf_doc[name].update()
        except Exception:
            pass

    def update_l2_containers(self):
        """Atualiza containers L2 (apenas Log)"""
        colors = self.theme_manager.get_theme_colors()
        # Atualizar apenas o log
        try:
            # log é um container com Text dentro
            if hasattr(self, 'detail_log') and self.detail_log and len(self.detail_log.content.controls) > 1:
                inner = self.detail_log.content.controls[1]
                if isinstance(inner, ft.Container) and hasattr(inner, 'content') and hasattr(inner.content, 'value'):
                    inner.content.value = self.detail_fields.get("Log", "")
                    inner.content.update()
        except Exception:
            pass

    def _update_detail_field(self, field_name: str, value: str):
        """Atualiza o dicionário detail_fields quando um campo editável muda."""
        self.detail_fields[field_name] = value
        # Marcar item atual como "sujo" e atualizar botão salvar correspondente
        if hasattr(self, 'selected_item') and self.selected_item:
            item_id = self.selected_item.get("ID")
            if item_id is not None:
                if not hasattr(self, 'dirty_items'):
                    self.dirty_items = set()
                self.dirty_items.add(item_id)
                # Atualizar cor do botão de salvar se existir
                if hasattr(self, 'card_save_buttons') and item_id in self.card_save_buttons:
                    btn = self.card_save_buttons[item_id]
                    try:
                        btn.icon_color = ft.Colors.ORANGE_400 if hasattr(ft.Colors, 'ORANGE_400') else ft.Colors.ORANGE
                        btn.tooltip = "Alterações não salvas"
                        btn.update()
                    except Exception:
                        pass

    def save_card_changes(self, item):
        """Persiste alterações editáveis do card selecionado e reseta estado sujo.
        Agora salva no banco de dados e registra mudanças no log.
        """
        try:
            if not item:
                return
            item_id = item.get("ID")
            if item_id is None:
                return
                
            # Buscar item atual do banco de dados para comparação
            existing_item = self.db_manager.get_item_from_db(item_id)
            
            # Encontrar item base em sample_data
            updated_data = {}
            for base in self.sample_data:
                if base.get("ID") == item_id:
                    # Campos editáveis que podem ser salvos
                    editable_fields = [
                        "Comments", "Continuity", "Link"
                    ]  # Expandir aqui se mais campos ficarem editáveis
                    
                    for f in editable_fields:
                        if f in self.detail_fields:
                            # Mapear campo para nome do banco de dados
                            db_field_map = {
                                'Comments': 'comments',
                                'Continuity': 'continuity', 
                                'Link': 'link_vpcr'
                            }
                            db_field = db_field_map.get(f, f.lower())
                            
                            old_value = existing_item.get(db_field, '') if existing_item else base.get(f, '')
                            new_value = self.detail_fields[f]
                            
                            # Atualizar em sample_data
                            base[f] = new_value
                            updated_data[f] = new_value
                            
                            # Registrar mudança no log se houve alteração
                            if str(old_value) != str(new_value):
                                self.db_manager.log_change(
                                    item_id=str(item_id), 
                                    field_name=db_field, 
                                    old_value=old_value, 
                                    new_value=new_value, 
                                    change_type='manual_update'
                                )
                    
                    # Adicionar ID aos dados para atualização
                    updated_data['ID'] = str(item_id)
                    
                    # Atualizar no banco de dados
                    self.db_manager.upsert_item(updated_data)
                    break
                    
            # Remover do conjunto de sujos
            if hasattr(self, 'dirty_items') and item_id in self.dirty_items:
                self.dirty_items.remove(item_id)
                
            # Atualizar botão salvar
            if hasattr(self, 'card_save_buttons') and item_id in self.card_save_buttons:
                btn = self.card_save_buttons[item_id]
                btn.icon_color = self.theme_manager.get_theme_colors()["accent"]
                btn.tooltip = "Salvar alterações deste card"
                try:
                    btn.update()
                except Exception:
                    pass
                    
            # Feedback visual usando a notificação personalizada
            self.show_custom_notification(
                f"✅ Card {item_id} salvo com sucesso!",
                color=ft.Colors.GREEN_400,
                duration=2000
            )
            
        except Exception as ex:
            print(f"Erro ao salvar card: {ex}")
            self.show_custom_notification(
                f"❌ Erro ao salvar card: {ex}",
                color=ft.Colors.RED_400,
                duration=4000
            )

    def _open_link(self):
        """Abre o link em uma nova janela do navegador"""
        import webbrowser
        link = self.detail_fields.get("Link", "").strip()
        if link:
            # Adiciona http:// se não estiver presente
            if not link.startswith(('http://', 'https://')):
                link = 'http://' + link
            try:
                webbrowser.open(link)
            except Exception as e:
                # Mostra uma mensagem de erro se não conseguir abrir o link
                self.page.show_snack_bar(
                    ft.SnackBar(
                        content=ft.Text(f"Erro ao abrir link: {str(e)}"),
                        bgcolor=ft.Colors.RED_400
                    )
                )
        else:
            # Mostra mensagem se o link estiver vazio
            self.page.show_snack_bar(
                ft.SnackBar(
                    content=ft.Text("Nenhum link disponível"),
                    bgcolor=ft.Colors.ORANGE_400
                )
            )

    def create_vpcr_tab(self):
        """Cria o conteúdo da aba VPCR"""
        colors = self.theme_manager.get_theme_colors()
        # Garantir que FilePicker esteja pronto
        try:
            self.file_import_manager.build_file_picker()
        except Exception:
            pass
        
        # Lista de cards com filtros (ListView para melhor comportamento de scroll)
        self.card_list = ft.ListView(
            controls=[self.create_card(item) for item in self.filtered_data],
            spacing=10,
            auto_scroll=False,
            expand=True
        )
        
        # Cabeçalho com filtros dentro de um Stack para overlay suspenso
        header_content = ft.Column([
            ft.Row([
                ft.Text(
                    "Filtros",
                    size=18,
                    weight=ft.FontWeight.BOLD,
                    color=colors["text_container_primary"],
                    expand=True
                ),
                # Agrupar os botões no canto: importar + limpar
                ft.Row([
                    ft.IconButton(
                        icon=ft.Icons.FILE_UPLOAD,
                        tooltip="Importar",
                        on_click=lambda e: self.open_import_dialog()
                    ),
                    ft.IconButton(icon=ft.Icons.DELETE_SWEEP, tooltip="Limpar filtros", on_click=self.clear_all_filters),
                    # Botão para ativar modo de seleção para exportar cards
                    ft.IconButton(icon=ft.Icons.FILE_PRESENT, tooltip="Selecionar cards para exportar", on_click=lambda e: self.toggle_card_select_mode())
                ], spacing=6)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Column([
                ft.Row([
                    self.filter_vpcr_chips,
                    self.filter_sourcing_manager_chips,
                    self.filter_status_chips,
                    self.filter_supplier_chips,
                    self.filter_requestor_chips,
                    self.filter_continuity_chips,
                    # Switch de TODOs ativos na mesma linha
                    ft.Container(
                        content=self.todos_filter_switch,
                        padding=ft.padding.symmetric(horizontal=8, vertical=4),
                        bgcolor=colors["field_bg"],
                        border=ft.border.all(1, colors["field_border"]),
                        border_radius=8,
                    )
                ], spacing=8, wrap=False, scroll=ft.ScrollMode.AUTO)
            ], spacing=8)
        ], spacing=10)

        header_container = ft.Container(
            content=ft.Stack(
                controls=[header_content, self.dropdown_panel_container],
                clip_behavior=ft.ClipBehavior.NONE
            ),
            bgcolor=colors["secondary"],
            padding=15,
            border_radius=10,
            margin=ft.margin.only(bottom=10),
            shadow=ft.BoxShadow(
                spread_radius=1,
                blur_radius=5,
                color=ft.Colors.BLACK12,
                offset=ft.Offset(0, 2)
            )
        )
        # Criar os controles de footer fora da expressão do Column para evitar erros de sintaxe
        self.card_export_count_text = ft.Text("", size=14, weight=ft.FontWeight.BOLD)
        self.card_export_footer = ft.Container(
            content=ft.Row([
                self.card_export_count_text,
                ft.Container(expand=True),
                ft.TextButton("Cancelar", on_click=lambda e: self.cancel_card_selection()),
                ft.ElevatedButton("Exportar", on_click=lambda e: self.export_selected_cards())
            ], alignment=ft.MainAxisAlignment.CENTER),
            bgcolor=colors["secondary"],
            padding=10,
            border_radius=8,
            visible=False
        )

        left_column = ft.Container(
            content=ft.Column([
                header_container,
                # Lista de cards
                ft.Container(
                    content=self.card_list,
                    border_radius=10,
                    expand=True
                ),
                # Footer para exportação em modo seleção de cards (referenciado em self)
                self.card_export_footer
            ], expand=True, tight=True),
            width=400,  # Largura fixa mais estreita para a coluna esquerda
            alignment=ft.alignment.top_left
        )
        
        # L1: Área superior (2/3 da altura)
        # VPCR Overview - TextFields com placeholder e alturas menores
        self.tf_title = ft.TextField(
            value=self.detail_fields.get("Title", ""),
            label="Title",
            text_style=ft.TextStyle(size=14, weight=ft.FontWeight.BOLD, color=colors["text_container_primary"]),
            bgcolor=colors["field_bg"],
            border_color=colors["field_border"],
            expand=True,
            multiline=True,
            min_lines=15,
            read_only=True
        )
        
        self.tf_initiated = ft.TextField(
            value=self.detail_fields.get("Initiated Date", ""), 
            label="Initiated Date", 
            text_style=ft.TextStyle(size=self.theme_manager.font_size, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"],
            height=40,
            expand=True,  # Garante que se adapte horizontalmente
            read_only=True
        )
        
        self.tf_last_update = ft.TextField(
            value=self.detail_fields.get("Last Update", ""), 
            label="Last Update", 
            text_style=ft.TextStyle(size=self.theme_manager.font_size, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"],
            height=40,
            expand=True,  # Garante que se adapte horizontalmente
            read_only=True
        )
        
        self.tf_closed_date = ft.TextField(
            value=self.detail_fields.get("Closed Date", ""), 
            label="Closed Date", 
            text_style=ft.TextStyle(size=self.theme_manager.font_size, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"],
            height=40,
            expand=True,  # Garante que se adapte horizontalmente
            read_only=True
        )
        
        self.tf_category = ft.TextField(
            value=self.detail_fields.get("Category", ""), 
            label="Category", 
            text_style=ft.TextStyle(size=self.theme_manager.font_size, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"],
            height=40,
            expand=True,  # Garante que se adapte horizontalmente
            read_only=True
        )
        
        self.tf_supplier = ft.TextField(
            value=self.detail_fields.get("Supplier", ""), 
            label="Supplier", 
            text_style=ft.TextStyle(size=self.theme_manager.font_size, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"],
            height=40,
            expand=True,  # Garante que se adapte horizontalmente
            read_only=True
        )
        
        self.tf_pns = ft.TextField(
            value=self.detail_fields.get("PNs", ""), 
            label="Part Numbers", 
            multiline=True, 
            min_lines=5,  # Altura mínima menor para permitir melhor adaptação
            text_style=ft.TextStyle(size=self.theme_manager.font_size, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"], 
            expand=True,
            read_only=True
        )
        
        self.tf_plants = ft.TextField(
            value=self.detail_fields.get("Plants Affected", ""), 
            label="Affected Plants", 
            multiline=True, 
            min_lines=5,  # Altura mínima menor para permitir melhor adaptação
            text_style=ft.TextStyle(size=self.theme_manager.font_size, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"], 
            expand=True,
            read_only=True
        )
        
        # Campo de Link com ícone para abrir página web
        self.tf_link = ft.TextField(
            value=self.detail_fields.get("Link", ""),
            label="Link",
            text_style=ft.TextStyle(size=12, color=colors["field_text"]),
            bgcolor=colors["field_bg"],
            border_color=colors["field_border"],
            height=40,
            expand=True,  # Garante que se adapte horizontalmente
            suffix=ft.IconButton(
                icon=ft.Icons.OPEN_IN_NEW,
                icon_size=16,
                tooltip="Abrir link",
                on_click=lambda e: self._open_link()
            ),
            on_change=lambda e: self._update_detail_field("Link", e.control.value)
        )
        
        # Campo de Comentários multilinha
        self.tf_comments = ft.TextField(
            value=self.detail_fields.get("Comments", ""), 
            label="Comentários",
            multiline=True, 
            min_lines=10,  # Altura mínima menor para permitir melhor adaptação
            text_style=ft.TextStyle(size=self.theme_manager.font_size, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"], 
            expand=True, 
            on_change=lambda e: self._update_detail_field("Comments", e.control.value)
        )

        # Mais espaçamento entre campos (spacing aumentado)
        # Organizando os campos com expansão específica
        overview_controls = [
            # Title - expansível (maior fator para empurrar campos abaixo)
            ft.Container(content=self.tf_title, expand=4),
            # Datas - altura fixa
            ft.Container(
                content=ft.Row([self.tf_initiated, self.tf_last_update], spacing=8)
            ),
            ft.Container(
                content=ft.Row([self.tf_closed_date, self.tf_category], spacing=8)
            ),
            # Fornecedor - altura fixa
            ft.Container(
                content=self.tf_supplier
            ),
            # PNs e Plantas - expansíveis (sem altura fixa)
            ft.Container(
                content=ft.Row([self.tf_pns, self.tf_plants], spacing=8),
                expand=3  # Maior fator de expansão para campos expansíveis
            ),
            # Link - altura fixa
            ft.Container(
                content=self.tf_link
            ),
            # Comentários - expansível (sem altura fixa)
            ft.Container(content=self.tf_comments, expand=3)  # Maior fator de expansão
        ]

        self.detail_overview = ft.Container(
            content=ft.Column(overview_controls, spacing=20, expand=True),
            bgcolor=colors["secondary"],
            padding=12,
            border_radius=8,
            expand=True
        )

        # Request & Responsibility - TextFields compactos com labels em português
        self.tf_requestor = ft.TextField(
            value=self.detail_fields.get("Requestor", ""), 
            label="Requestor", 
            text_style=ft.TextStyle(size=self.theme_manager.font_size, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"], 
            expand=True, 
            height=40,
            read_only=True
        )
        
        self.tf_sourcing = ft.TextField(
            value=self.detail_fields.get("Sourcing", ""), 
            label="Sourcing", 
            text_style=ft.TextStyle(size=self.theme_manager.font_size, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"], 
            expand=True, 
            height=40,
            read_only=True
        )
        
        self.tf_sqie = ft.TextField(
            value=self.detail_fields.get("SQIE", ""), 
            label="SQIE", 
            text_style=ft.TextStyle(size=12, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"], 
            expand=True, 
            height=40,
            read_only=True
        )
        
        self.tf_continuity = ft.TextField(
            value=self.detail_fields.get("Continuity", ""), 
            label="Continuity", 
            text_style=ft.TextStyle(size=12, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"], 
            expand=True, 
            height=40, 
            on_change=lambda e: self._update_detail_field("Continuity", e.control.value)
        )

        # Organizar Responsibles em duas colunas
        request_col1 = [self.tf_requestor, self.tf_sourcing]
        request_col2 = [self.tf_sqie, self.tf_continuity]

        self.detail_request = ft.Container(
            content=ft.Row([
                ft.Column(request_col1, spacing=20, expand=True),
                ft.Column(request_col2, spacing=20, expand=True)
            ], spacing=12),
            bgcolor=colors["secondary"],
            padding=12,
            border_radius=8,
            expand=True,
            height=120  # Altura reduzida para layout com 2 colunas
        )

        # Documentation - criar TextFields organizados em 4 colunas
        doc_fields = [
            ("RFQ", False), ("DRA", False), ("DQR", False), ("LOI", False), ("Tooling", False), ("Drawing", False),
            ("PO Alfa", False), ("SR", False), ("Deviation", False), ("PO Beta", False), ("PPAP", False), ("GBPA", False), ("EDI", False), ("SCR", False),
            ("", False), ("", False)  # Campos invisíveis para alinhamento
        ]
        self.tf_doc = {}
        
        # Criar os TextFields
        invisible_counter = 0
        for name, editable in doc_fields:
            if name == "":  # Campos invisíveis
                tf = ft.Container(height=40)  # Container vazio com mesma altura dos campos
                self.tf_doc[f"invisible_{invisible_counter}"] = tf
                invisible_counter += 1
            else:
                tf = ft.TextField(
                    value=self.detail_fields.get(name, ""), 
                    label=name, 
                    text_style=ft.TextStyle(size=self.theme_manager.font_size, color=colors["field_text"]), 
                    bgcolor=colors["field_bg"], 
                    border_color=colors["field_border"], 
                    expand=True, 
                    height=40, 
                    on_change=lambda e, n=name: self._update_detail_field(n, e.control.value)
                )
                self.tf_doc[name] = tf

        # Organizar em quatro colunas
        col1_fields = []
        col2_fields = []
        col3_fields = []
        col4_fields = []
        
        # Criar lista de chaves para acessar os campos (incluindo invisíveis)
        field_keys = []
        invisible_counter = 0
        for name, _ in doc_fields:
            if name == "":
                field_keys.append(f"invisible_{invisible_counter}")
                invisible_counter += 1
            else:
                field_keys.append(name)
        
        fields_per_column = 4  # Agora temos exatamente 4 campos por coluna (16 total)
        
        for i, field_key in enumerate(field_keys):
            if i < 4:
                col1_fields.append(self.tf_doc[field_key])
            elif i < 8:
                col2_fields.append(self.tf_doc[field_key])
            elif i < 12:
                col3_fields.append(self.tf_doc[field_key])
            else:
                col4_fields.append(self.tf_doc[field_key])

        self.detail_doc = ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Column(col1_fields, spacing=20, expand=True),
                    ft.Column(col2_fields, spacing=20, expand=True),
                    ft.Column(col3_fields, spacing=20, expand=True),
                    ft.Column(col4_fields, spacing=20, expand=True)
                ], spacing=12)
            ], expand=True, scroll=ft.ScrollMode.ADAPTIVE),
            bgcolor=colors["secondary"],
            padding=12,
            border_radius=8,
            expand=True
        )

        # L2: Log com largura dos containers Request e Documentation e metade da altura
        
        # Container do Overview
        left_top = ft.Container(
            content=ft.Column([
                ft.Text("VPCR Overview", size=14, weight=ft.FontWeight.BOLD, color=colors["text_container_primary"]),
                self.detail_overview
            ], spacing=6, expand=True),
            expand=True,
            padding=ft.padding.all(10)
        )
        self.detail_log = ft.Container(
            content=ft.Container(
                content=ft.Text(self.detail_fields.get("Log", ""), size=12, color=colors["text_container_secondary"]), 
                expand=True, 
                alignment=ft.alignment.top_left
            ), 
            bgcolor=colors["secondary"], 
            padding=12, 
            border_radius=8, 
            expand=True  # Log expandirá para ocupar a largura disponível
        )

        # Linha de Status com ícones e texto abaixo
        status_items = [
            ("Draft", True),
            ("Preliminary Change\nManager Review", True),
            ("Preliminary\nReview", True), 
            ("Cross Functional\nReview", False),
            ("Secondary Change\nManager Review", False),
            ("Pending Resource\nAssignment", False),
            ("Cost and Lead Time\nAnalysis", False),
            ("Engineering\nWork in Progress", False),
            ("Purchasing\nWork in Progress", False),
            ("Pending Plant\nImplementation", False),
            ("Work\nComplete", False)
        ]
        
        # Criar ícones para cada status
        status_icons = []
        for status_text, is_completed in status_items:
            # Texto exibido: remover quebras manuais e deixar o wrap natural em até 2 linhas
            display_text = status_text.replace("\n", " ")
            # Ícone de status
            icon = ft.Icon(
                ft.Icons.CHECK_CIRCLE if is_completed else ft.Icons.RADIO_BUTTON_UNCHECKED,
                color=ft.Colors.GREEN if is_completed else colors["surface"],  # Cor do tema para elementos desativados
                size=22  # ligeiramente menor para reduzir altura total
            )

            status_icons.append(
                ft.Container(
                    content=ft.Column([
                        icon,
                        ft.Container(
                            content=ft.Text(
                                display_text,
                                size=10,
                                color=colors["text_container_primary"],
                                text_align=ft.TextAlign.CENTER,
                                max_lines=2,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                tooltip=status_text
                            ),
                            height=28,  # altura aproximada para 2 linhas de fonte size=9
                            alignment=ft.alignment.center
                        )
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=2),
                    padding=ft.padding.symmetric(horizontal=4, vertical=2),
                    alignment=ft.alignment.center,
                    expand=True
                )
            )

        # Criar controles finais com linhas conectando os ícones
        final_status_controls = []
        for i, icon_container in enumerate(status_icons):
            final_status_controls.append(icon_container)
            # Adicionar linha entre ícones (exceto após o último)
            if i < len(status_icons) - 1:
                # Verificar se ambos os ícones adjacentes estão verdes
                current_completed = status_items[i][1]
                next_completed = status_items[i + 1][1]
                line_color = ft.Colors.GREEN if (current_completed and next_completed) else colors["surface"]
                
                # Linha conectando os ícones
                connecting_line = ft.Container(
                    content=ft.Divider(height=2, color=line_color),
                    width=40,  # Largura maior da linha
                    alignment=ft.alignment.center,
                    height=22,  # Altura do ícone para alinhar com o centro
                    padding=ft.padding.only(top=10)  # Padding para passar pelo centro do ícone
                )
                final_status_controls.append(connecting_line)

        # Container da linha de status agora sem expand para abraçar o conteúdo (altura mínima)
        status_line = ft.Container(
            content=ft.Row(
                controls=final_status_controls,
                spacing=0,  # Espaçamento zero pois as linhas têm largura própria
                alignment=ft.MainAxisAlignment.START
            ),
            bgcolor=colors["secondary"],
            padding=6,  # Reduzido de 12 para 6
            border_radius=8,
            margin=ft.margin.only(bottom=10)
        )

        # Layout final: Status line acima, depois Overview à esquerda e coluna direita com Request/Documentation/Log
        main_content = ft.Container(
            content=ft.Column([
                status_line,  # Linha de status no topo
                ft.Row([
                    left_top,  # Overview - toda altura à esquerda
                    ft.Column([
                        ft.Container(
                            content=ft.Column([
                                ft.Text("Request & Responsibility", size=14, weight=ft.FontWeight.BOLD, color=colors["text_container_primary"]),
                                self.detail_request
                            ], spacing=6),
                            padding=ft.padding.all(10)
                        ),
                        ft.Container(
                            content=ft.Column([
                                ft.Text("Documentation", size=14, weight=ft.FontWeight.BOLD, color=colors["text_container_primary"]),
                                self.detail_doc
                            ], spacing=6),
                            padding=ft.padding.all(10)
                        ),
                        ft.Container(
                            content=ft.Column([
                                ft.Text("Log", size=14, weight=ft.FontWeight.BOLD, color=colors["text_container_primary"]),
                                self.detail_log
                            ], spacing=6),
                            expand=1,
                            padding=ft.padding.all(10)
                        )
                    ], spacing=10, expand=True)
                ], spacing=15, expand=True)
            ], spacing=0, expand=True),
            expand=True,
            alignment=ft.alignment.top_left
        )
        
        # Armazenar conteúdo principal de detalhes
        self.detail_main_content = main_content

        # Placeholder quando nenhum card estiver selecionado
        placeholder_colors = self.theme_manager.get_theme_colors()
        self.no_selection_placeholder = ft.Container(
            content=ft.Column([
                ft.Icon(ft.Icons.TOC, size=70, color=placeholder_colors.get("surface", ft.Colors.GREY)),
                ft.Text(
                    "Nenhum card selecionado",
                    size=20,
                    weight=ft.FontWeight.BOLD,
                    color=placeholder_colors.get("text_secondary", ft.Colors.GREY_400)
                ),
                ft.Text(
                    "Selecione um card à esquerda para visualizar os detalhes.",
                    size=14,
                    color=placeholder_colors.get("text_secondary", ft.Colors.GREY_500),
                    text_align=ft.TextAlign.CENTER
                )
            ], alignment=ft.MainAxisAlignment.CENTER, horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=20),
            expand=True,
            bgcolor=placeholder_colors.get("secondary", "#2d2d2d"),
            border_radius=8,
            padding=20,
            alignment=ft.alignment.center
        )

        # Contêiner do painel direito que será trocado entre placeholder e detalhes
        self.right_panel = ft.Container(
            content=self.detail_main_content if getattr(self, 'selected_item', None) else self.no_selection_placeholder,
            expand=True
        )

        # Retornar layout final
        return ft.Container(
            content=ft.Row([
                left_column,
                self.right_panel
            ], spacing=15, expand=True, alignment=ft.MainAxisAlignment.START, tight=True),
            expand=True,
            padding=10,
            alignment=ft.alignment.top_left
        )
    
    def open_import_dialog(self):
        """Abre janela de importação utilizando FileImportManager."""
        # Verificar dependência
        if openpyxl is None:
            self.page.snack_bar = ft.SnackBar(
                content=ft.Text("Biblioteca openpyxl não instalada. Execute 'pip install openpyxl'."),
                bgcolor=ft.Colors.RED_400
            )
            self.page.snack_bar.open = True
            self.page.update()
        self.file_import_manager.open_import_window()
        
    
    def create_settings_tab(self):
        """Cria o conteúdo da aba Settings"""
        colors = self.theme_manager.get_theme_colors()
        
        def change_theme(e):
            theme_name = e.control.value
            self.theme_manager.set_theme(theme_name)
            
            # Mostrar notificação via snackbar
            theme_names = {
                "dark": "Dark Theme",
                "dracula": "Dracula Theme", 
                "light_dracula": "Light Dracula Theme"
            }
            
            snack_bar = ft.SnackBar(
                content=ft.Text(f"Tema alterado para: {theme_names.get(theme_name, theme_name)}"),
                action="OK",
                action_color=self.theme_manager.get_theme_colors()["accent"]
            )
            self.page.snack_bar = snack_bar
            snack_bar.open = True
            
            self.apply_theme()
            # Recriar componentes com novo tema
            self.create_components()
            # Atualizar a página completamente
            self.page.clean()
            self.main(self.page)
        
        # Theme selector
        theme_selector = ft.RadioGroup(
            content=ft.Column([
                ft.Radio(value="dark", label="Dark Theme", label_style=ft.TextStyle(color=colors["cor_font_settings"])),
                ft.Radio(value="dracula", label="Dracula Theme", label_style=ft.TextStyle(color=colors["cor_font_settings"])),
                ft.Radio(value="light_dracula", label="Light Dracula Theme", label_style=ft.TextStyle(color=colors["cor_font_settings"]))
            ]),
            value=self.theme_manager.current_theme,
            on_change=change_theme
        )

        # Font size slider
        def change_font_size(e):
            size = int(e.control.value)
            self.theme_manager.set_font_size(size)
            
            # Mostrar notificação
            snack_bar = ft.SnackBar(
                content=ft.Text(f"Tamanho da fonte alterado para: {size}px"),
                action="OK",
                action_color=self.theme_manager.get_theme_colors()["accent"]
            )
            self.page.snack_bar = snack_bar
            snack_bar.open = True
            
            # Atualizar apenas os componentes que usam fonte, sem recriar a página
            self.update_detail_containers()
            self.page.update()
        
        font_size_slider = ft.Column([
            ft.Text("Tamanho da Fonte dos TextFields", size=16, weight=ft.FontWeight.BOLD, color=colors["cor_font_settings"]),
            ft.Slider(
                min=10,
                max=24,
                value=self.theme_manager.font_size,
                divisions=14,
                label="{value}px",
                on_change_end=change_font_size,
                active_color=colors["accent"],
                inactive_color=colors["surface"]
            ),
            ft.Text(f"Tamanho atual: {self.theme_manager.font_size}px", 
                   size=12, 
                   color=colors["text_secondary"])
        ], spacing=8)

        # Campos configuráveis visíveis nos cards
        fields_checkboxes = []
        for field in self.db_headers:
            if field == "ID":
                continue
            cb = ft.Checkbox(
                label=field, 
                value=(field in self.visible_fields),
                label_style=ft.TextStyle(color=colors["cor_font_settings"])
            )
            fields_checkboxes.append(cb)

        def apply_visible_fields(e):
            # Atualizar visible_fields com base nos checkboxes
            self.visible_fields = [cb.label for cb in fields_checkboxes if cb.value]
            # Salvar configuração
            self.save_visible_fields()
            self.update_card_list(preserve_scroll=True)
            # notificação
            sb = ft.SnackBar(content=ft.Text("Campos visíveis atualizados"))
            self.page.snack_bar = sb
            sb.open = True

        apply_button = ft.ElevatedButton(text="Aplicar Campos", on_click=apply_visible_fields)

        # Containers separados com scroll: tema | campos
        theme_container = ft.Container(
            content=ft.Column([
                ft.Text("Tema da Aplicação", size=18, weight=ft.FontWeight.BOLD, color=colors["cor_font_settings"]),
                ft.Divider(),
                ft.Container(content=ft.Column([theme_selector], scroll=ft.ScrollMode.AUTO), expand=False),
                ft.Divider(),
                font_size_slider
            ], spacing=10),
            bgcolor=colors["secondary"],
            padding=12,
            border_radius=8,
            width=360,
            height=400  # Aumentado para acomodar o controle de fonte
        )

        fields_container = ft.Container(
            content=ft.Column([
                ft.Text("Campos visíveis nos cards", size=18, weight=ft.FontWeight.BOLD, color=colors["text_container_primary"]),
                ft.Divider(),
                ft.Container(content=ft.Column(fields_checkboxes, spacing=6, scroll=ft.ScrollMode.AUTO), expand=True),
                ft.Row([apply_button], alignment=ft.MainAxisAlignment.END)
            ], spacing=10),
            bgcolor=colors["secondary"],
            padding=12,
            border_radius=8,
            width=360,
            height=400  # Igualado com o tema_container para manter consistência visual
        )

        # Layout responsivo: duas colunas quando couber, coluna única se pequeno
        settings_layout = ft.Row([
            theme_container,
            fields_container
        ], spacing=20, wrap=True)

        return ft.Container(
            content=ft.Column([
                ft.Text("Settings", size=20, weight=ft.FontWeight.BOLD, color=colors["text_primary"]),
                settings_layout
            ], spacing=16),
            expand=True,
            padding=20
        )

def main():
    app = VPCRApp()
    ft.app(target=app.main)

if __name__ == "__main__":
    main()
