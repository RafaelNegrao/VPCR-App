import flet as ft
import json
import os

class ThemeManager:
    """Gerenciador de temas da aplicação"""
    
    def __init__(self):
        self.themes = {
            "dark": {
                "primary": "#121212",
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
                "field_border": "#444444"
            },
            "dracula": {
                "primary": "#282a36",
                "secondary": "#44475a",
                "surface": "#6272a4",
                "on_surface": "#f8f8f2",
                "on_primary": "#f8f8f2",
                "accent": "#b783ff",
                "card_bg": "#44475a",
                "border": "#6272a4",
                "text_primary": "#f8f8f2",           # Texto fora de containers
                "text_secondary": "#8be9fd",          # Texto secundário fora de containers
                "text_container_primary": "#f8f8f2",    # Texto principal dentro de containers
                "text_container_secondary": "#8be9fd",  # Texto secundário dentro de containers
                "field_bg": "#44475a",
                "field_text": "#8be9fd",
                "field_border": "#6272a4"
            },
            "light_dracula": {
                "primary": "#f8f8f2",
                "secondary": "#e6e6fa",
                "surface": "#bd93f9",
                "on_surface": "#282a36",
                "on_primary": "#282a36",
                "accent": "#bd93f9",
                "card_bg": "#ffffff",
                "border": "#bd93f9",
                "text_primary": "#282a36",        # Texto fora de containers
                "text_secondary": "#6272a4",      # Texto secundário fora de containers
                "text_container_primary": "#282a36",   # Texto principal dentro de containers
                "text_container_secondary": "#44475a", # Texto secundário dentro de containers
                "field_bg": "#ffffff",
                "field_text": "#282a36",
                "field_border": "#bd93f9"
            }
        }
        self.current_theme = "dark"
        self.load_theme()
    
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

class VPCRApp:
    def __init__(self):
        self.theme_manager = ThemeManager()
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

        # Dados de exemplo (cada item corresponde ao header acima)
        self.sample_data = [
            {"ID": 1, "Title": "Item 1", "Description": "Descrição do item 1", "Status": "Ativo", "Sourcing Manager": "Alice", "Supplier": "Supplier A", "Requestor": "John", "Continuity": "High"},
            {"ID": 2, "Title": "Item 2", "Description": "Descrição do item 2", "Status": "Inativo", "Sourcing Manager": "Bob", "Supplier": "Supplier B", "Requestor": "Mary", "Continuity": "Low"},
            {"ID": 3, "Title": "Item 3", "Description": "Descrição do item 3", "Status": "Ativo", "Sourcing Manager": "Alice", "Supplier": "Supplier C", "Requestor": "Peter", "Continuity": "Medium"},
            {"ID": 4, "Title": "Item 4", "Description": "Descrição do item 4", "Status": "Pendente", "Sourcing Manager": "Carlos", "Supplier": "Supplier A", "Requestor": "John", "Continuity": "High"},
            {"ID": 5, "Title": "Item 5", "Description": "Outro item", "Status": "Ativo", "Sourcing Manager": "Diana", "Supplier": "Supplier B", "Requestor": "Mary", "Continuity": "Low"},
        ]
        self.filtered_data = self.sample_data.copy()
        # Campos visíveis nos cards (configurável nas Settings)
        self.visible_fields = ["Title", "Description", "Status", "Sourcing Manager", "Supplier"]
        
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
        
    def main(self, page: ft.Page):
        self.page = page
        self.page.title = "VPCR App"
        self.page.window_min_width = 1200
        self.page.window_min_height = 800
        
        # Aplicar tema inicial
        self.apply_theme()
        
        # Criar componentes
        self.create_components()
        
        # Adicionar o painel dropdown ao overlay da página para ficar suspenso
        self.page.overlay.append(self.dropdown_panel_container)
        
        # Layout principal
        self.page.add(
            ft.Container(
                content=ft.Tabs(
                    tabs=[
                        ft.Tab(
                            text="VPCR",
                            content=self.create_vpcr_tab()
                        ),
                        ft.Tab(
                            text="Settings",
                            content=self.create_settings_tab()
                        )
                    ],
                    selected_index=0,
                    animation_duration=300,
                    label_color=self.theme_manager.get_theme_colors()["accent"],
                    indicator_color=self.theme_manager.get_theme_colors()["accent"]
                ),
                bgcolor=self.theme_manager.get_theme_colors()["primary"],
                expand=True,
                padding=10
            )
        )
    
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
    
    def create_components(self):
        """Cria os componentes da interface"""
        colors = self.theme_manager.get_theme_colors()
        
        # --- filtros com multiseleção usando Chips ---
        # containers para chips de multiseleção
        # Larguras fixas para cada filtro (usadas para posicionar o dropdown customizado)
        self.filter_widths = {
            "Sourcing Manager": 180,
            "Status": 120,
            "Supplier": 150,
            "Requestor": 150,
            "Continuity": 120,
        }
        self.filter_order = [
            "Sourcing Manager",
            "Status",
            "Supplier",
            "Requestor",
            "Continuity",
        ]
        # Define uma altura padronizada para todos os filtros
        filter_height = 38  # Altura fixa para todos os filtros
        
        self.filter_sourcing_manager_chips = ft.Container(
            content=ft.Text("Sourcing Manager: Carregando...", size=12, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
            bgcolor=colors["field_bg"],
            border=ft.border.all(1, colors["field_border"]),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            width=180,
            height=filter_height
        )
        
        self.filter_status_chips = ft.Container(
            content=ft.Text("Status: Carregando...", size=12, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
            bgcolor=colors["field_bg"],
            border=ft.border.all(1, colors["field_border"]),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            width=120,
            height=filter_height
        )
        
        self.filter_supplier_chips = ft.Container(
            content=ft.Text("Supplier: Carregando...", size=12, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
            bgcolor=colors["field_bg"],
            border=ft.border.all(1, colors["field_border"]),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            width=150,
            height=filter_height
        )
        
        self.filter_requestor_chips = ft.Container(
            content=ft.Text("Requestor: Carregando...", size=12, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
            bgcolor=colors["field_bg"],
            border=ft.border.all(1, colors["field_border"]),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            width=150,
            height=filter_height
        )
        
        self.filter_continuity_chips = ft.Container(
            content=ft.Text("Continuity: Carregando...", size=12, no_wrap=True, overflow=ft.TextOverflow.ELLIPSIS),
            bgcolor=colors["field_bg"],
            border=ft.border.all(1, colors["field_border"]),
            border_radius=8,
            padding=ft.padding.symmetric(horizontal=12, vertical=8),
            width=120,
            height=filter_height
        )
        
        # armazenamento das seleções
        self.filter_selections = {
            "Sourcing Manager": set(),
            "Status": set(),
            "Supplier": set(),
            "Requestor": set(),
            "Continuity": set()
        }
        # Popular opções únicas a partir dos dados
        self.populate_filter_options()

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
        sm_sel = self.filter_selections.get("Sourcing Manager", set())
        status_multi_sel = self.filter_selections.get("Status", set())
        supplier_sel = self.filter_selections.get("Supplier", set())
        requestor_sel = self.filter_selections.get("Requestor", set())
        continuity_sel = self.filter_selections.get("Continuity", set())
        
        self.filtered_data = []
        for item in self.sample_data:
            def matches_multi(selected_set, value):
                if not selected_set:  # nada selecionado = mostrar todos
                    return True
                return value in selected_set

            sm_match = matches_multi(sm_sel, item.get("Sourcing Manager", ""))
            status_multi_match = matches_multi(status_multi_sel, item.get("Status", ""))
            supplier_match = matches_multi(supplier_sel, item.get("Supplier", ""))
            requestor_match = matches_multi(requestor_sel, item.get("Requestor", ""))
            continuity_match = matches_multi(continuity_sel, item.get("Continuity", ""))
            
            if sm_match and status_multi_match and supplier_match and requestor_match and continuity_match:
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
        
        self.update_card_list()
    
    def create_card(self, item):
        """Cria um card para um item"""
        colors = self.theme_manager.get_theme_colors()
        # obter status e cor do status
        status_val = item.get("Status", "")
        status_color = {
            "Ativo": ft.Colors.GREEN,
            "Inativo": ft.Colors.RED,
            "Pendente": ft.Colors.ORANGE
        }.get(status_val, ft.Colors.GREY)

        # construir conteúdo do card dinamicamente conforme visible_fields
        rows = []

        # primeira linha: mostrar Title e, se presente, o badge de Status
        title_text = item.get("Title", "")
        first_row_controls = [
            ft.Text(title_text, size=16, weight=ft.FontWeight.BOLD, color=colors["text_container_primary"], expand=True)
        ]
        if "Status" in self.visible_fields:
            first_row_controls.append(
                ft.Container(
                    content=ft.Text(status_val, size=12, color=ft.Colors.WHITE),
                    bgcolor=status_color,
                    padding=ft.padding.symmetric(horizontal=8, vertical=2),
                    border_radius=10
                )
            )

        rows.append(ft.Row(first_row_controls, alignment=ft.MainAxisAlignment.SPACE_BETWEEN))

        # outras fields (excluir Title já mostrado)
        for f in self.visible_fields:
            if f in ("Title", "Status"):
                continue
            val = item.get(f, "")
            if val != "":
                rows.append(ft.Row([ft.Text(f + ":", size=12, weight=ft.FontWeight.BOLD, color=colors["text_container_primary"]), ft.Text(str(val), size=12, color=colors["text_container_secondary"])], spacing=8))

        return ft.Card(
            content=ft.Container(
                content=ft.Column(rows, spacing=6),
                padding=15,
                expand=True,
                on_click=lambda e: self.select_item(item)
            ),
            color=colors["card_bg"],
            shadow_color=ft.Colors.BLACK26,
            elevation=2
        )
    
    def update_card_list(self):
        """Atualiza a lista de cards"""
        if hasattr(self, 'card_list'):
            # ListView usa `controls` também
            self.card_list.controls.clear()
            for item in self.filtered_data:
                self.card_list.controls.append(self.create_card(item))
            self.card_list.update()

    def populate_filter_options(self):
        """Popula as opções dos filtros com chips de multiseleção"""
        # coletar valores únicos
        sourcing_vals = sorted({item.get("Sourcing Manager", "") for item in self.sample_data if item.get("Sourcing Manager", "")})
        status_vals = sorted({item.get("Status", "") for item in self.sample_data if item.get("Status", "")})
        supplier_vals = sorted({item.get("Supplier", "") for item in self.sample_data if item.get("Supplier", "")})
        requestor_vals = sorted({item.get("Requestor", "") for item in self.sample_data if item.get("Requestor", "")})
        continuity_vals = sorted({item.get("Continuity", "") for item in self.sample_data if item.get("Continuity", "")})

        colors = self.theme_manager.get_theme_colors()

        # armazenar valores para uso posterior
        self.filter_options = {
            "Sourcing Manager": sourcing_vals,
            "Status": status_vals,
            "Supplier": supplier_vals,
            "Requestor": requestor_vals,
            "Continuity": continuity_vals
        }

        def create_clickable_filter(field_name, container):
            def show_dropdown(e):
                self.show_dropdown_panel(field_name)

            container.content = ft.Row([
                ft.Text(f"{field_name}: Todos", size=12, color=colors["field_text"], expand=True),
                ft.Icon(ft.Icons.ARROW_DROP_DOWN, size=16, color=colors["field_text"])
            ])
            container.on_click = show_dropdown

        # criar containers clicáveis para cada filtro
        create_clickable_filter("Sourcing Manager", self.filter_sourcing_manager_chips)
        create_clickable_filter("Status", self.filter_status_chips)
        create_clickable_filter("Supplier", self.filter_supplier_chips)
        create_clickable_filter("Requestor", self.filter_requestor_chips)
        create_clickable_filter("Continuity", self.filter_continuity_chips)
        
        # atualizar controles se já estiverem na página
        try:
            self.filter_sourcing_manager_chips.update()
            self.filter_status_chips.update()
            self.filter_supplier_chips.update()
            self.filter_requestor_chips.update()
            self.filter_continuity_chips.update()
        except:
            pass

    def show_dropdown_panel(self, field_name: str):
        """Mostra um painel dropdown customizado abaixo do filtro clicado (com busca e checkboxes)."""
        colors = self.theme_manager.get_theme_colors()
        values = self.filter_options.get(field_name, [])

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

        # Construir painel
        panel = ft.Container(
            bgcolor=colors["secondary"],
            border=ft.border.all(1, colors["field_border"]),
            border_radius=8,
            padding=10,
            content=ft.Column([
                ft.Row([
                    ft.IconButton(icon=ft.Icons.CLEAR_ALL, tooltip="Limpar tudo", on_click=clear_all),
                    ft.IconButton(icon=ft.Icons.SELECT_ALL, tooltip="Selecionar todos", on_click=select_all),
                    ft.IconButton(icon=ft.Icons.CHECK_BOX_OUTLINE_BLANK, tooltip="Desmarcar todos", on_click=deselect_all),
                ], spacing=4, alignment=ft.MainAxisAlignment.START),
                ft.TextField(
                    label="Buscar...",
                    on_change=lambda e: apply_search_filter(e.control.value),
                    autofocus=True
                ),
                ft.Container(
                    content=ft.Column(checkboxes, tight=True, scroll=ft.ScrollMode.AUTO),
                    height=260,
                    width=self.filter_widths.get(field_name, 200)
                ),
                ft.Row([
                    ft.TextButton("Cancelar", on_click=cancel_and_close),
                    ft.ElevatedButton("Aplicar", on_click=apply_and_close)
                ], alignment=ft.MainAxisAlignment.END)
            ], spacing=10)
        )

        # Posicionamento: calcular deslocamento à esquerda baseado na ordem e larguras
        left_offset = 0
        spacing = 8  # mesmo spacing da Row
        for name in self.filter_order:
            if name == field_name:
                break
            left_offset += self.filter_widths.get(name, 0) + spacing

        # Calcular coordenadas absolutas para posicionar a janela suspensa
        # Obter a posição global dos filtros (aproximadamente 25px do topo do app + padding)
        filter_top_position = 110  # Valor ajustado para posicionar abaixo dos filtros
        
        # Configurar o contêiner do painel para posicionamento absoluto no overlay
        self.dropdown_panel_container.left = left_offset + 15  # padding do contêiner principal
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
        self.filter_data()

    def update_filter_display(self, field_name):
        """Atualiza o display do filtro com base nas seleções"""
        colors = self.theme_manager.get_theme_colors()
        selected = self.filter_selections[field_name]
        
        # encontrar o container correto
        container_map = {
            "Sourcing Manager": self.filter_sourcing_manager_chips,
            "Status": self.filter_status_chips,
            "Supplier": self.filter_supplier_chips,
            "Requestor": self.filter_requestor_chips,
            "Continuity": self.filter_continuity_chips
        }
        container = container_map.get(field_name)
        
        if container and container.content and len(container.content.controls) > 0:
            if not selected:
                text = f"{field_name}: Todos"
            elif len(selected) == 1:
                text = f"{field_name}: {list(selected)[0]}"
            else:
                text = f"{field_name}: {len(selected)} selecionados"
            
            container.content.controls[0].value = text
            container.update()

    def close_dialog(self, dlg):
        dlg.open = False
        self.page.update()

    def select_item(self, item):
        """Atualiza os campos detalhados com base no item selecionado"""
        self.selected_item = item
        
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
                        on_click=self.open_import_dialog if hasattr(self, 'open_import_dialog') else None
                    ),
                    ft.IconButton(icon=ft.Icons.DELETE_SWEEP, tooltip="Limpar filtros", on_click=self.clear_all_filters)
                ], spacing=6)
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ft.Column([
                ft.Row([
                    self.filter_sourcing_manager_chips,
                    self.filter_status_chips,
                    self.filter_supplier_chips,
                    self.filter_requestor_chips,
                    self.filter_continuity_chips
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

        left_column = ft.Container(
            content=ft.Column([
                header_container,
                # Lista de cards
                ft.Container(
                    content=self.card_list,
                    border_radius=10,
                    expand=True
                )
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
            on_change=lambda e: self._update_detail_field("Title", e.control.value)
        )
        
        self.tf_initiated = ft.TextField(
            value=self.detail_fields.get("Initiated Date", ""), 
            label="Data de Início", 
            text_style=ft.TextStyle(size=12, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"], 
            expand=True, 
            height=36, 
            on_change=lambda e: self._update_detail_field("Initiated Date", e.control.value)
        )
        
        self.tf_last_update = ft.TextField(
            value=self.detail_fields.get("Last Update", ""), 
            label="Última Atualização", 
            text_style=ft.TextStyle(size=12, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"], 
            expand=True, 
            height=36, 
            on_change=lambda e: self._update_detail_field("Last Update", e.control.value)
        )
        
        self.tf_closed_date = ft.TextField(
            value=self.detail_fields.get("Closed Date", ""), 
            label="Data de Fechamento", 
            text_style=ft.TextStyle(size=12, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"], 
            expand=True, 
            height=36, 
            on_change=lambda e: self._update_detail_field("Closed Date", e.control.value)
        )
        
        self.tf_category = ft.TextField(
            value=self.detail_fields.get("Category", ""), 
            label="Categoria", 
            text_style=ft.TextStyle(size=12, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"], 
            expand=True, 
            height=36, 
            on_change=lambda e: self._update_detail_field("Category", e.control.value)
        )
        
        self.tf_supplier = ft.TextField(
            value=self.detail_fields.get("Supplier", ""), 
            label="Fornecedor", 
            text_style=ft.TextStyle(size=12, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"], 
            expand=True, 
            height=36, 
            on_change=lambda e: self._update_detail_field("Supplier", e.control.value)
        )
        
        self.tf_pns = ft.TextField(
            value=self.detail_fields.get("PNs", ""), 
            label="Part Numbers", 
            multiline=True, 
            text_style=ft.TextStyle(size=12, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"], 
            expand=True, 
            on_change=lambda e: self._update_detail_field("PNs", e.control.value)
        )
        
        self.tf_plants = ft.TextField(
            value=self.detail_fields.get("Plants Affected", ""), 
            label="Plantas Afetadas", 
            multiline=True, 
            text_style=ft.TextStyle(size=12, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"], 
            expand=True, 
            on_change=lambda e: self._update_detail_field("Plants Affected", e.control.value)
        )
        
        # Campo de Link com ícone para abrir página web
        self.tf_link = ft.TextField(
            value=self.detail_fields.get("Link", ""),
            label="Link",
            text_style=ft.TextStyle(size=12, color=colors["field_text"]),
            bgcolor=colors["field_bg"],
            border_color=colors["field_border"],
            expand=True,
            height=36,
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
            text_style=ft.TextStyle(size=12, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"], 
            expand=True, 
            on_change=lambda e: self._update_detail_field("Comments", e.control.value)
        )

        # Mais espaçamento entre campos (spacing aumentado)
        # Organizando os campos com expansão específica
        overview_controls = [
            # Title - expansível
            ft.Container(content=self.tf_title, expand=True),
            # Datas - altura fixa
            ft.Row([self.tf_initiated, self.tf_last_update], spacing=18),
            ft.Row([self.tf_closed_date, self.tf_category], spacing=18),
            # Fornecedor - altura fixa
            self.tf_supplier,
            # PNs e Plantas - expansíveis
            ft.Container(
                content=ft.Row([self.tf_pns, self.tf_plants], spacing=18),
                expand=True
            ),
            # Link - altura fixa
            self.tf_link,
            # Comentários - expansível
            ft.Container(content=self.tf_comments, expand=True)
        ]

        self.detail_overview = ft.Container(
            content=ft.Column(overview_controls, spacing=8, expand=True),
            bgcolor=colors["secondary"],
            padding=12,
            border_radius=8,
            expand=True
        )

        # Request & Responsibility - TextFields compactos com labels em português
        self.tf_requestor = ft.TextField(
            value=self.detail_fields.get("Requestor", ""), 
            label="Solicitante", 
            text_style=ft.TextStyle(size=12, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"], 
            expand=True, 
            height=36, 
            on_change=lambda e: self._update_detail_field("Requestor", e.control.value)
        )
        
        self.tf_sourcing = ft.TextField(
            value=self.detail_fields.get("Sourcing", ""), 
            label="Sourcing", 
            text_style=ft.TextStyle(size=12, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"], 
            expand=True, 
            height=36, 
            on_change=lambda e: self._update_detail_field("Sourcing", e.control.value)
        )
        
        self.tf_sqie = ft.TextField(
            value=self.detail_fields.get("SQIE", ""), 
            label="SQIE", 
            text_style=ft.TextStyle(size=12, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"], 
            expand=True, 
            height=36, 
            on_change=lambda e: self._update_detail_field("SQIE", e.control.value)
        )
        
        self.tf_continuity = ft.TextField(
            value=self.detail_fields.get("Continuity", ""), 
            label="Continuidade", 
            text_style=ft.TextStyle(size=12, color=colors["field_text"]), 
            bgcolor=colors["field_bg"], 
            border_color=colors["field_border"], 
            expand=True, 
            height=36, 
            on_change=lambda e: self._update_detail_field("Continuity", e.control.value)
        )

        # Mostrar como coluna com espaçamento maior entre campos
        request_controls = [
            self.tf_requestor,
            self.tf_sourcing,
            self.tf_sqie,
            self.tf_continuity
        ]

        self.detail_request = ft.Container(
            content=ft.Column(request_controls, spacing=8),
            bgcolor=colors["secondary"],
            padding=12,
            border_radius=8,
            expand=True
        )

        # Documentation - criar TextFields organizados em 2 colunas
        doc_fields = [
            ("RFQ", False), ("DRA", False), ("DQR", False), ("LOI", False), ("Tooling", False), ("Drawing", False),
            ("PO Alfa", False), ("SR", False), ("Deviation", False), ("PO Beta", False), ("PPAP", False), ("GBPA", False), ("EDI", False), ("SCR", False)
        ]
        self.tf_doc = {}
        
        # Criar os TextFields
        for name, editable in doc_fields:
            tf = ft.TextField(
                value=self.detail_fields.get(name, ""), 
                label=name, 
                text_style=ft.TextStyle(size=12, color=colors["field_text"]), 
                bgcolor=colors["field_bg"], 
                border_color=colors["field_border"], 
                expand=True, 
                height=36, 
                on_change=lambda e, n=name: self._update_detail_field(n, e.control.value)
            )
            self.tf_doc[name] = tf

        # Organizar em duas colunas
        left_column_fields = []
        right_column_fields = []
        
        field_names = [name for name, _ in doc_fields]
        mid_point = len(field_names) // 2
        
        for i, field_name in enumerate(field_names):
            if i < mid_point:
                left_column_fields.append(self.tf_doc[field_name])
            else:
                right_column_fields.append(self.tf_doc[field_name])

        self.detail_doc = ft.Container(
            content=ft.Row([
                ft.Column(left_column_fields, spacing=8, expand=True),
                ft.Column(right_column_fields, spacing=8, expand=True)
            ], spacing=12),
            bgcolor=colors["secondary"],
            padding=12,
            border_radius=8,
            expand=True
        )

        # L1: agrupar Overview, Request e Documentation numa linha horizontal
        left_top = ft.Container(
            content=ft.Column([
                ft.Text("VPCR Overview", size=14, weight=ft.FontWeight.BOLD, color=colors["text_container_primary"]),
                self.detail_overview
            ], spacing=6, expand=True),
            expand=True,
            padding=ft.padding.all(10)
        )
        
        middle_top = ft.Container(
            content=ft.Column([
                ft.Text("Request & Responsibility", size=14, weight=ft.FontWeight.BOLD, color=colors["text_container_primary"]),
                self.detail_request
            ], spacing=6, expand=True),
            expand=True,
            padding=ft.padding.all(10)
        )
        
        right_top = ft.Container(
            content=ft.Column([
                ft.Text("Documentation", size=14, weight=ft.FontWeight.BOLD, color=colors["text_container_primary"]),
                self.detail_doc
            ], spacing=6, expand=True),
            expand=True,
            padding=ft.padding.all(10)
        )

        # L2: Log com largura dos containers Request e Documentation e metade da altura
        self.detail_log = ft.Container(
            content=ft.Column([
                ft.Text("Log", size=14, weight=ft.FontWeight.BOLD, color=colors["text_container_primary"]), 
                ft.Container(
                    content=ft.Text(self.detail_fields.get("Log", ""), size=12, color=colors["text_container_secondary"]), 
                    expand=True, 
                    alignment=ft.alignment.top_left
                )
            ], spacing=6), 
            bgcolor=colors["secondary"], 
            padding=12, 
            border_radius=8, 
            expand=True  # Log expandirá para ocupar a largura disponível
        )

        # Layout final: Overview ocupa toda altura, Request/Documentation/Log na lateral direita
        main_content = ft.Container(
            content=ft.Row([
                left_top,  # Overview - toda altura
                ft.Column([
                    ft.Row([
                        middle_top,  # Request & Responsibility
                        right_top    # Documentation
                    ], spacing=10, expand=True),
                    ft.Container(
                        content=self.detail_log,  # Log ocupará metade da altura
                        expand=True,  # Permite que o Log se expanda verticalmente
                        padding=ft.padding.all(10)
                    )
                ], spacing=10, expand=True)
            ], spacing=15, expand=True),
            expand=True,
            alignment=ft.alignment.top_left
        )
        
        return ft.Container(
            content=ft.Row([
                left_column,
                main_content
            ], spacing=15, expand=True, alignment=ft.MainAxisAlignment.START, tight=True),
            expand=True,
            padding=10,
            alignment=ft.alignment.top_left
        )
    
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
                ft.Radio(value="dark", label="Dark Theme"),
                ft.Radio(value="dracula", label="Dracula Theme"),
                ft.Radio(value="light_dracula", label="Light Dracula Theme")
            ]),
            value=self.theme_manager.current_theme,
            on_change=change_theme
        )

        # Campos configuráveis visíveis nos cards
        fields_checkboxes = []
        for field in self.db_headers:
            if field == "ID":
                continue
            cb = ft.Checkbox(label=field, value=(field in self.visible_fields))
            fields_checkboxes.append(cb)

        def apply_visible_fields(e):
            # Atualizar visible_fields com base nos checkboxes
            self.visible_fields = [cb.label for cb in fields_checkboxes if cb.value]
            self.update_card_list()
            # notificação
            sb = ft.SnackBar(content=ft.Text("Campos visíveis atualizados"))
            self.page.snack_bar = sb
            sb.open = True

        apply_button = ft.ElevatedButton(text="Aplicar Campos", on_click=apply_visible_fields)

        # Containers separados com scroll: tema | campos
        theme_container = ft.Container(
            content=ft.Column([
                ft.Text("Tema da Aplicação", size=18, weight=ft.FontWeight.BOLD, color=colors["text_container_primary"]),
                ft.Divider(),
                ft.Container(content=ft.Column([theme_selector], scroll=ft.ScrollMode.AUTO), expand=True)
            ], spacing=10),
            bgcolor=colors["secondary"],
            padding=12,
            border_radius=8,
            width=360,
            height=300
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
            height=300
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
