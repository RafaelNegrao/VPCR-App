# VPCR Tracker App

Aplicativo desktop construído com [Flet](https://flet.dev/) para centralizar o acompanhamento de projetos VPCR, organizar cards por status, analisar indicadores e controlar importações de planilhas. O projeto utiliza SQLite como persistência local e oferece um fluxo completo para inspeção, filtros, dashboards e ajustes de tema.

## ✨ Principais funcionalidades

- **Gerenciamento de cards VPCR**: visualização estilo Kanban com filtros dinâmicos por status, fornecedor, sourcing manager e outras dimensões.
- **Importação de planilhas Excel**: valida cabeçalhos seguindo o modelo oficial, registra inconsistências e persiste os dados no banco `vpcr_database.db`.
- **Indicadores interativos**: aba dedicada com métricas resumidas, percentuais e rankings (status, tipos, suppliers e responsáveis).
- **Registro de TODOs e log**: acompanha atividades pendentes e histórico de alterações por item.
- **Temas personalizáveis**: seleção entre temas Dark, Dracula e Light Dracula diretamente na aba Settings.
- **Build nativo para Windows**: geração de executável `.exe` via PyInstaller com ícones personalizados.

## 🛠 Arquitetura em alto nível

| Camada | Tecnologia | Observações |
| --- | --- | --- |
| Interface | Flet (Flutter + Python) | Layout responsivo, `ft.Tabs`, `ft.ResponsiveRow`, animações de ícones. |
| Regras de negócio | `main.py` | Contém `VPCRApp`, gerenciadores de importação, temas e banco. |
| Persistência | SQLite (`vpcr_database.db`) | Tabelas VPCR, TODOs e log; modo WAL ativo para concorrência. |
| Importação | `openpyxl` (opcional) | Lê planilhas `.xlsx/.xlsm`, valida cabeçalhos e colunas obrigatórias. |

## ✅ Pré-requisitos

- Python 3.11 ou superior (recomendado 3.13, já usado para desenvolvimento).
- `pip` atualizado.
- Sistema Windows (build do executável utiliza PyInstaller com ícones `.ico`).
- Arquivo `vpcr_database.db` presente na raiz do projeto.

## 🚀 Configuração do ambiente

```powershell
# 1. (Opcional) criar ambiente virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2. Instalar dependências principais
pip install flet openpyxl

# 3. Dependências adicionais para empacotamento
pip install pyinstaller
```

> 💡 `openpyxl` é opcional, mas necessário para importar planilhas. Caso o pacote não esteja instalado, a aplicação exibirá uma mensagem orientando o usuário.

## ▶️ Execução local

```powershell
cd "C:\Users\Rafael\Desktop\VPCR App"
python main.py
```

A janela principal abrirá com três abas:

1. **VPCR** – Cards, filtros, painel de detalhes, TODOs e logs.
2. **Indicadores** – Resumo com métricas totais, distribuições percentuais e rankings “Top 5”.
3. **Settings** – Seleção de tema, fonte e atalhos para importação.

## 📥 Importação de dados Excel

1. Abra a aba **VPCR** e clique em **Importar Arquivos VPCR**.
2. Selecione arquivos `.xlsx` ou `.xlsm` com o cabeçalho oficial (célula A1 = `VPCR Project ID`, coluna T = `Last Updated Date`).
3. O gerenciador valida o layout, acusa divergências e grava os registros no banco.
4. Após a importação, use **Recarregar** para atualizar os cards e os indicadores.

## 📊 Indicadores disponibilizados

- **Resumo Geral**: total de VPCRs, número de status distintos, fornecedores ativos e sourcing managers.
- **Distribuições**: barras com percentuais por status e tipo de VPCR.
- **Rankings**: Top 5 Suppliers e Top 5 Sourcing Managers.
- **Continuity**: panorama das classificações de continuidade logo abaixo da distribuição por tipo.

Todos os cards utilizam `ft.ProgressBar`, ícones temáticos e layout responsivo (`ft.ResponsiveRow`) para adaptação em diferentes resoluções.

## 🗂 Estrutura simplificada

```text
VPCR App/
├── main.py                 # Lógica principal do app Flet
├── vpcr_database.db        # Banco SQLite com dados VPCR
├── comandos.txt            # Comando PyInstaller de referência
├── cummins.ico / process.ico
├── build/                  # Artefatos gerados pelo PyInstaller
├── VPCR Tracker app.exe    # Executável gerado (quando disponível)
└── README.md               # Este arquivo
```

## 📦 Gerando o executável para Windows

Com o ambiente virtual ativado e o pacote `pyinstaller` instalado, execute:

```powershell
pyinstaller --onefile --windowed --icon "process.ico" --add-data "cummins.ico;." --name "VPCR Tracker app" main.py
```

O executável será gerado em `dist/VPCR Tracker app.exe`. Ícones adicionais são empacotados via `--add-data`.

## 🧰 Dicas e resolução de problemas

- **Mensagem “Biblioteca openpyxl não instalada”**: rode `pip install openpyxl` e reinicie o app.
- **Banco bloqueado**: o modo WAL cria arquivos `vpcr_database.db-wal`/`-shm`; feche o app antes de mover o banco.
- **Atualização de indicadores**: use o botão de recarregar dados após importar planilhas ou editar registros diretamente no banco.
- **Build falhou**: verifique se a linha de comando do PyInstaller corresponde ao caminho atual e se os ícones `.ico` existem na raiz.

## 📄 Licença

Distribuído sob a licença [MIT](LICENSE). Consulte o arquivo para detalhes.
