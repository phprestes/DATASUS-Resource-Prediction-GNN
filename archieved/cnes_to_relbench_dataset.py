import duckdb
import os
import glob
import zipfile
import shutil
from tqdm import tqdm

# --- CONFIGURAÇÕES ---
INPUT_FOLDER = './zips_cnes'
DB_PATH = 'cnes_relbench.duckdb'
TEMP_EXTRACT_DIR = './temp_extract'
EXPORT_PARQUET_DIR = './relbench_dataset'

# --- MAPEAMENTO COMPLETO (Baseado no Dicionário de Dados) ---
# Mapeia prefixo do CSV -> Nome da Tabela no Schema RAW
CSV_MAPPING = {
    # === NÓS PRINCIPAIS (Entidades) ===
    'tbestabelecimento': 'raw_estabelecimento',       # [cite: 58] LFCES004
    'tbDadosProfissionalSus': 'raw_profissional',     # [cite: 201] LFCES018
    'tbEquipe': 'raw_equipe',                         # [cite: 327] LFCES037
    'tbMantenedora': 'raw_mantenedora',               # [cite: 87] LFCES005

    # === ARESTAS DE VÍNCULO (Quem conecta com quem) ===
    'tbCargaHorariaSus': 'raw_vinculo_prof_estab',    #  LFCES021 (Profissional -> Estab)
    'rlEstabEquipeProf': 'raw_vinculo_prof_equipe',   # [cite: 343] LFCES038 (Profissional -> Equipe)
    'rlEquipeNasfEsf': 'raw_vinculo_nasf_esf',        # [cite: 546] LFCES059 (Equipe -> Equipe)
    'rlEstabOrgParc': 'raw_organizacao_parceira',     # [cite: 694] LFCES079 (Estab -> Org)

    # === FATOS E CARACTERÍSTICAS (Atributos do Estabelecimento) ===
    'rlEstabComplementar': 'raw_leitos',              # [cite: 49] LFCES002 (Capacidade)
    'rlEstabEquipamento': 'raw_equipamentos',         # [cite: 233] LFCES020 (Tecnologia)
    'rlEstabServClass': 'raw_servico_especializado',  #  LFCES032 (Complexidade Médica)
    'rlEstabProgFundo': 'raw_gestao_nivel',           # [cite: 110] LFCES007 (Gestão)
    'rlEstabAtendPrestConv': 'raw_atendimento_conv',  # [cite: 104] LFCES006 (Convênios)
    'rlEstabSipac': 'raw_habilitacoes_incentivos',    # [cite: 426] LFCES045, 046, 053 (Financeiro)
    'rlEstabServicoApoio': 'raw_servico_apoio',       # [cite: 129] LFCES009 (Apoio Logístico)
    
    # === FATOS DE ALTA COMPLEXIDADE (Serviços Específicos) ===
    'tbDialise': 'raw_dialise',                       # [cite: 138] LFCES012
    'tbQuimioRadio': 'raw_quimio_radio',              # [cite: 156] LFCES013
    'tbHemoterapia': 'raw_hemoterapia',               # [cite: 266] LFCES027
    
    # === FATOS DE INFRAESTRUTURA ===
    'rlEstabInstFisiAssist': 'raw_instalacao_fisica', # [cite: 190] LFCES015
    'rlEstabSamu': 'raw_veiculos_samu',               # [cite: 719] LFCES081
    'rlEstabUnidAcolhim': 'raw_unid_acolhimento',     # [cite: 729] LFCES082
    'rlEstabAtenPsico': 'raw_atencao_psico',          # [cite: 760] LFCES084 (CAPS)
    
    # === QUALIDADE E AUDITORIA ===
    'rlEstabAvaliacao': 'raw_avaliacao',              # [cite: 808] LFCES091
    'tbEstabHorarioAtend': 'raw_horario_func',        # [cite: 857] LFCES098
}

def setup_database(con):
    con.execute("CREATE SCHEMA IF NOT EXISTS raw;")
    con.execute("CREATE SCHEMA IF NOT EXISTS relbench;")

def ingest_raw_data(con):
    """
    Fase 1: Ingestão Tolerante a Falhas.
    Lê tudo como VARCHAR para evitar quebras por mudança de tipo.
    """
    os.makedirs(TEMP_EXTRACT_DIR, exist_ok=True)
    zip_files = sorted(glob.glob(os.path.join(INPUT_FOLDER, 'BASE_DE_DADOS_CNES_*.ZIP')))
    
    print(f"📦 Iniciando Ingestão RAW de {len(zip_files)} arquivos...")

    for zip_path in tqdm(zip_files, desc="Processando ZIPs"):
        try:
            filename = os.path.basename(zip_path)
            # Extrai YYYYMM (Competência)
            competencia = ''.join(filter(str.isdigit, filename))[-6:]
            
            with zipfile.ZipFile(zip_path, 'r') as z:
                file_list = z.namelist()
                
                # Itera sobre o nosso mapa expandido
                for csv_prefix, table_name in CSV_MAPPING.items():
                    # Busca case-insensitive no ZIP
                    matches = [f for f in file_list if csv_prefix.lower() in f.lower() and f.lower().endswith('.csv')]
                    
                    if not matches: continue
                    
                    target_csv = matches[0]
                    temp_csv_path = os.path.join(TEMP_EXTRACT_DIR, target_csv)
                    full_table_name = f"raw.{table_name}"
                    
                    try:
                        z.extract(target_csv, TEMP_EXTRACT_DIR)
                        
                        # Verifica existência
                        table_exists = con.execute(
                            f"SELECT count(*) FROM information_schema.tables WHERE table_schema = 'raw' AND table_name = '{table_name}'"
                        ).fetchone()[0]

                        # Parâmetros de Leitura Segura (Latin1 + All Varchar)
                        read_sql = f"""
                            SELECT *, '{competencia}' as competencia_mes 
                            FROM read_csv('{temp_csv_path}', 
                                header=True, sep=';', quote='"', 
                                all_varchar=True, encoding='latin-1', 
                                normalize_names=True, ignore_errors=True
                            )
                        """

                        if not table_exists:
                            con.execute(f"CREATE TABLE {full_table_name} AS {read_sql}")
                        else:
                            # Idempotência: limpa a competência se já existir e reinsere
                            # Verifica se coluna competencia_mes existe antes de deletar
                            cols = [c[0] for c in con.execute(f"DESCRIBE {full_table_name}").fetchall()]
                            if 'competencia_mes' in cols:
                                con.execute(f"DELETE FROM {full_table_name} WHERE competencia_mes = '{competencia}'")
                            
                            con.execute(f"INSERT INTO {full_table_name} {read_sql}")

                    except Exception as e:
                        # Loga o erro mas não para o script (tolerância a falhas)
                        # tqdm.write(f"[ALERTA] Erro na tabela {table_name} em {competencia}: {e}")
                        pass
                    finally:
                        if os.path.exists(temp_csv_path):
                            os.remove(temp_csv_path)

        except Exception as e:
            print(f"[ERRO CRÍTICO] ZIP {zip_path}: {e}")

def transform_nodes_and_edges(con):
    """
    Fase 2: Transformação Relacional para Grafos.
    Aqui separamos NÓS (IDs únicos) de FATOS (Séries Temporais).
    """
    print("\n⚙️ Construindo Grafo Relacional (Nodes & Temporal Facts)...")

    # --- 1. NÓS (ENTIDADES ÚNICAS) ---
    # Estratégia: Pegar o ID distinto e os atributos da data mais recente (arg_max)
    
    # Nó Estabelecimento [cite: 58]
    con.execute("DROP TABLE IF EXISTS relbench.node_estabelecimento")
    con.execute("""
        CREATE TABLE relbench.node_estabelecimento AS
        SELECT 
            co_unidade,
            arg_max(no_fantasia, competencia_mes) as nome_fantasia,
            arg_max(co_municipio_gestor, competencia_mes) as co_municipio,
            arg_max(co_natureza_jur, competencia_mes) as natureza_juridica
        FROM raw.raw_estabelecimento
        GROUP BY co_unidade
    """)
    print("   -> Nó 'Estabelecimento' criado.")

    # Nó Profissional [cite: 201]
    con.execute("DROP TABLE IF EXISTS relbench.node_profissional")
    con.execute("""
        CREATE TABLE relbench.node_profissional AS
        SELECT 
            co_profissional_sus,
            arg_max(no_profissional, competencia_mes) as nome,
            arg_max(co_cns, competencia_mes) as cns
        FROM raw.raw_profissional
        GROUP BY co_profissional_sus
    """)
    print("   -> Nó 'Profissional' criado.")

    # --- 2. ARESTAS TEMPORAIS (Vínculos) ---
    
    # Vínculo: Profissional trabalha em Estabelecimento 
    con.execute("DROP TABLE IF EXISTS relbench.edge_vinculo_trabalho")
    con.execute("""
        CREATE TABLE relbench.edge_vinculo_trabalho AS
        SELECT
            co_profissional_sus as source_id,
            co_unidade as target_id,
            strptime(competencia_mes || '01', '%Y%m%d') as timestamp,
            co_cbo,
            ind_vinculacao,
            tp_sus_nao_sus
        FROM raw.raw_vinculo_prof_estab
    """)
    print("   -> Aresta 'Trabalha Em' criada.")

    # --- 3. FATOS TEMPORAIS (Atributos Dinâmicos) ---
    # Convertemos tabelas de detalhes em tabelas temporais ligadas ao ID do Nó
    
    # Fato: Serviços Especializados  (Indicador crítico de complexidade)
    con.execute("DROP TABLE IF EXISTS relbench.fact_servicos")
    con.execute("""
        CREATE TABLE relbench.fact_servicos AS
        SELECT
            co_unidade,
            strptime(competencia_mes || '01', '%Y%m%d') as timestamp,
            co_servico,
            co_classificacao,
            tp_caracteristica -- Próprio ou Terceirizado
        FROM raw.raw_servico_especializado
    """)

    # Fato: Leitos [cite: 49]
    con.execute("DROP TABLE IF EXISTS relbench.fact_leitos")
    con.execute("""
        CREATE TABLE relbench.fact_leitos AS
        SELECT
            co_unidade,
            strptime(competencia_mes || '01', '%Y%m%d') as timestamp,
            co_leito,
            co_tipo_leito,
            TRY_CAST(qt_exist AS INTEGER) as qt_exist,
            TRY_CAST(qt_sus AS INTEGER) as qt_sus
        FROM raw.raw_leitos
    """)

    # Fato: Equipamentos [cite: 233]
    con.execute("DROP TABLE IF EXISTS relbench.fact_equipamentos")
    con.execute("""
        CREATE TABLE relbench.fact_equipamentos AS
        SELECT
            co_unidade,
            strptime(competencia_mes || '01', '%Y%m%d') as timestamp,
            co_equipamento,
            TRY_CAST(qt_existente AS INTEGER) as qt_exist,
            TRY_CAST(qt_uso AS INTEGER) as qt_uso
        FROM raw.raw_equipamentos
    """)
    print("   -> Tabelas de Fatos (Serviços, Leitos, Equipamentos) criadas.")

def export_to_parquet(con):
    print(f"\n💾 Exportando para {EXPORT_PARQUET_DIR}...")
    os.makedirs(EXPORT_PARQUET_DIR, exist_ok=True)
    
    tables = con.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'relbench'").fetchall()
    
    for (tbl,) in tables:
        output_path = os.path.join(EXPORT_PARQUET_DIR, f"{tbl}.parquet")
        con.execute(f"COPY relbench.{tbl} TO '{output_path}' (FORMAT PARQUET)")
        print(f"   -> {tbl}.parquet salvo.")

def main():
    con = duckdb.connect(DB_PATH)
    setup_database(con)
    ingest_raw_data(con)
    transform_nodes_and_edges(con)
    export_to_parquet(con)
    
    # Limpeza final
    if os.path.exists(TEMP_EXTRACT_DIR):
        shutil.rmtree(TEMP_EXTRACT_DIR)
    con.close()
    print("\n✅ Processo Completo! O Dataset RelBench está pronto.")

if __name__ == "__main__":
    main()