from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
RAW_FOLDER = BASE_DIR / 'data' / '01_raw'
INTERMEDIATE_FOLDER = BASE_DIR / 'data' / '02_intermediate'
PRIMARY_FOLDER = BASE_DIR / 'data' / '03_primary'
TEMP_EXTRACT_DIR = BASE_DIR / 'data' / 'temp_extract'

FACT_TABLES = [
    "rlEstabComplementar",
    "tbEstabelecimento",
    "tbMantenedora",
    "rlEstabAtendPrestConv",
    "rlEstabProgFundo",
    "rlEstabColetaSelRejeito",
    "rlEstabServicoApoio",
    "tbDialise",
    "tbQuimioRadio",
    "rlEstabComissaoOutro",
    "rlEstabInstFisiAssist",
    "tbDadosProfissionalSus",
    "tbServicoReferenciado",
    "rlEstabEquipamento",
    "tbCargaHorariaSus",
    "tbHemoterapia",
    "rlEstabServClass",
    "rlCooperativa",
    "tbEquipe",
    "rlEstabEquipeProf",
    "tbResidenciaMed",
    "tbSegmento",
    "tbArea",
    "tbEquipeChDifer",
    "tbEquipeAtendCompl",
    "rlEstabSipac",
    "tbProfResidencia",
    "rlEstabSubTipo",
    "rlEstabEndCompl",
    "tbEstabBanco",
    "rlEquipeNasfEsf",
    "rlEstabPoloAldeia",
    "rlEstabRepresentante",
    "rlJustifPtProf",
    "rlJustifPtProfLog",
    "rlEstabEquipeMun",
    "rlNasfEsf",
    "rlEstabTeleCnes",
    "rlEstabOrgParc",
    "rlEstabCentralReg",
    "rlEstabSamu",
    "rlEstabUnidAcolhim",
    "rlMunUnidAcolhim",
    "rlEstabAtenPsico",
    "rlMunAtenPsico",
    "rlEstabRegimeRes",
    "rlMunRegimeRes",
    "rlEstabAvaliacao",
    "rlAdmGerenciaCnes",
    "rlEstabEqpUnidApoio",
    "rlEstabEqpEmbarcacao",
    "tbJustificaDesligaPrf",
    "tbEstabHorarioAtend",
    "tbLocalGerenteAdministrador",
    "rlEstabProfComissao",
    "tbEstabAtivSecundaria",
    "rlEquipeAldeia"
]

CNES_USEFUL_COLUMNS = {
    "rlEstabComplementar": [
        "co_unidade",
        "co_leito",
        "co_tipo_leito",
        "qt_exist",
        "qt_sus",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "tbEstabelecimento": [
        "co_unidade",
        "co_cnes",
        "nu_cnpj_mantenedora",
        "tp_pfpj",
        "nivel_dep",
        "co_cep",
        "co_regiao_saude",
        "co_clientela",
        "tp_unidade",
        "co_turno_atendimento",
        "co_estado_gestor",
        "co_municipio_gestor",
        "to_chardt_atualizacaoddmmyyyy",
        "co_motivo_desab",
        "nu_latitude",
        "nu_longitude",
        "co_natureza_jur",
        "tp_estab_sempre_aberto",
        "st_conexao_internet",
        "co_tipo_estabelecimento",
        "co_atividade_principal",
        "st_contrato_formalizado",
        "tp_gestao"
    ],
    "tbMantenedora": [
        "nu_cnpj_mantenedora",
        "co_banco",
        "co_cep",
        "co_municipio",
        "co_regiao_saude",
        "st_fms_fes",
        "co_natureza_jur",
        "to_chardt_atualizacaoddmmyyyy",
        "co_gestor",
        "co_municipio_mant"
    ],
    "rlEstabAtendPrestConv": [
        "co_unidade",
        "co_atendimento_prestado",
        "co_convenio",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEstabProgFundo": [
        "co_unidade",
        "co_atividade",
        "tp_estadual_municipal",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEstabColetaSelRejeito": [
        "co_unidade",
        "co_coleta_rejeito",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEstabServicoApoio": [
        "co_unidade",
        "co_servico_apoio",
        "co_caracteristica",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "tbDialise": [
        "co_unidade",
        "qt_sala_hbsag_pos",
        "qt_sala_hbsag_neg",
        "qt_sala_dpi",
        "qt_sala_dpac",
        "qt_sala_reag_pos",
        "qt_sala_reag_neg",
        "qt_sala_rehcv",
        "nu_maqh_prop",
        "nu_maqh_outr",
        "tp_filtro_areia",
        "tp_filtro_carvao",
        "tp_abrandador",
        "tp_deoinizador",
        "tp_osmose_reversa",
        "tp_outros_trat_agua",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "tbQuimioRadio": [
        "co_unidade",
        "nu_salarsimu",
        "nu_salarplan",
        "nu_slararmfo",
        "nu_slarconfm",
        "nu_slarmolde",
        "nu_slarbolcp",
        "nu_slaqarmaz",
        "nu_slaqprepa",
        "nu_slaqcdura",
        "nu_slaqldura",
        "nu_slacpflul",
        "qt_eqrsimula",
        "qt_eqracell6",
        "qt_eqr_6seme",
        "qt_eqr_6come",
        "qt_rortv1050",
        "qt_rorv50150",
        "qt_rov150500",
        "qt_runidcoba",
        "qt_eqrbrbaix",
        "qt_eqrbrmedi",
        "qt_eqrbralta",
        "qt_eqrmonita",
        "qt_eqrmoniti",
        "qt_eqrsispln",
        "qt_eqrdoscli",
        "qt_eqrfonsel",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEstabComissaoOutro": [
        "co_unidade",
        "co_comissao",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEstabInstFisiAssist": [
        "co_unidade",
        "co_instalacao",
        "qt_instalacao",
        "nu_leitos",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "tbDadosProfissionalSus": [
        "co_profissional_sus",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "tbServicoReferenciado": [
        "co_unidade",
        "co_servico_referenciado",
        "tp_servico_referenciado",
        "co_cnpj",
        "co_municipio",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEstabEquipamento": [
        "co_unidade",
        "co_equipamento",
        "co_tipo_equipamento",
        "qt_existente",
        "qt_uso",
        "tp_sus",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "tbCargaHorariaSus": [
        "co_unidade",
        "co_profissional_sus",
        "co_cbo",
        "tp_sus_nao_sus",
        "ind_vinculacao",
        "qt_carga_horaria_ambulatorial",
        "qt_carga_hor_hosp_sus",
        "qt_carga_horaria_outros",
        "tp_preceptor",
        "tp_residente",
        "to_charadt_atualizacaoddmmyyyy"
    ],
    "tbHemoterapia": [
        "co_unidade",
        "nu_srecepcad",
        "nu_striaghmt",
        "nu_striagcln",
        "nu_scoleta",
        "nu_saferese",
        "nu_sprestoq",
        "nu_sproces",
        "nu_sestoque",
        "nu_sdistrib",
        "nu_sorologia",
        "nu_simunohem",
        "nu_spretranf",
        "nu_shemostas",
        "nu_scontrolq",
        "nu_sbiomolec",
        "nu_simunfen",
        "nu_stransfus",
        "nu_ssgdoador",
        "qt_ecadrecli",
        "qt_ecentrefr",
        "qt_erfguasng",
        "qt_econgrapd",
        "qt_eextaplsm",
        "qt_efreez18",
        "qt_efreez30",
        "qt_eagitplqt",
        "qt_eseladora",
        "qt_eirradhem",
        "qt_eagltnosc",
        "qt_emaqafres",
        "qt_erfgareag",
        "qt_erfgamsts",
        "qt_ecapfllam",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEstabServClass": [
        "co_unidade",
        "co_servico",
        "co_classificacao",
        "tp_caracteristica",
        "co_cnpjcpf",
        "co_ambulatorial",
        "co_ambulatorial_sus",
        "co_hospitalar",
        "co_hospitalar_sus",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlCooperativa": [
        "co_unidade",
        "co_cooperativa",
        "co_cbo",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "tbEquipe": [
        "co_municipio",
        "co_area",
        "seq_equipe",
        "co_unidade",
        "tp_equipe",
        "dt_ativacao",
        "dt_desativacao",
        "tp_pop_assist_quilomb",
        "tp_pop_assist_assent",
        "tp_pop_assist_geral",
        "tp_pop_assist_escola",
        "tp_pop_assist_pronasci",
        "tp_pop_assist_indigena",
        "tp_pop_assist_ribeirinha",
        "tp_pop_assist_situacao_rua",
        "tp_pop_assist_priv_liberdade",
        "tp_pop_assist_conflito_lei",
        "tp_pop_assist_adol_conf_lei",
        "cd_motivo_desativ",
        "cd_tp_desativ",
        "co_equipe",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEstabEquipeProf": [
        "co_municipio",
        "co_area",
        "seq_equipe",
        "co_profissional_sus",
        "co_unidade",
        "co_cbo",
        "tp_sus_nao_sus",
        "ind_vinculacao",
        "co_microarea",
        "dt_entrada",
        "dt_desligamento",
        "st_equipeminima",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "tbResidenciaMed": [
        "co_unidade",
        "sq_residencia",
        "co_municipio",
        "co_cep",
        "nu_cuidadores",
        "nu_capacidade_masc",
        "nu_capacidade_fem",
        "tp_sus_nao_sus",
        "dt_ativacao",
        "dt_desativacao",
        "st_parceria_ong",
        "nu_cnpj_ong",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "tbSegmento": [
        "co_municipio",
        "co_segmento",
        "tp_segmento",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "tbArea": [
        "co_municipio",
        "co_area",
        "cd_segmento",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEstabSipac": [
        "co_unidade",
        "cod_sub_grupo_habilitacao",
        "cmtp_inicio",
        "cmtp_fim",
        "nu_leitos",
        "to_chardt_atualizacaoddmmyyyy",
        "tp_habilitacao"
    ],
    "tbProfResidencia": [
        "co_unidade",
        "nu_residencia",
        "co_profissional_sus",
        "co_cbo",
        "ind_vinculacao",
        "tp_sus_nao_sus",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEstabSubTipo": [
        "co_unidade",
        "co_tipo_unidade",
        "co_sub_tipo_unidade",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEquipeNasfEsf": [
        "co_municipio",
        "co_area",
        "seq_equipe",
        "co_municipio_esf",
        "co_area_esf",
        "seq_equipe_esf",
        "nu_sequencial",
        "co_unidade",
        "tp_equipe_esf",
        "co_cnes_esf",
        "co_segmento_esf",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEstabPoloAldeia": [
        "co_unidade",
        "co_aldeia",
        "co_polobase",
        "co_dsei",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEstabCentralReg": [
        "co_unidade",
        "co_seq_central",
        "co_subtipo_central",
        "co_municipio_end",
        "dt_ativacao",
        "dt_desativacao",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEstabSamu": [
        "co_unidade",
        "dt_ativacao",
        "co_unidade_central",
        "co_seq_central",
        "co_prefixo_aeronave",
        "nu_embarca_marinha",
        "dt_desativacao",
        "co_desativacao",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEstabUnidAcolhim": [
        "co_unidade",
        "sq_acolhimento",
        "tp_acolhimento",
        "co_municipio",
        "co_cep",
        "tp_estrutura",
        "st_parceria_ong",
        "nu_cnpj_ong",
        "nu_vagas",
        "co_profissional_sus",
        "co_cbo",
        "tp_sus_nao_sus",
        "ind_vinculacao",
        "dt_ativacao",
        "dt_desativacao",
        "st_unidade_regional",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlMunUnidAcolhim": [
        "co_unidade",
        "co_municipio",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEstabAtenPsico": [
        "co_unidade",
        "tp_estrutura",
        "st_parceria_ong",
        "nu_cnpj_ong",
        "nu_vagas_acol_notur",
        "co_profissional_sus",
        "co_cbo",
        "tp_sus_nao_sus",
        "ind_vinculacao",
        "co_cnes_referencia",
        "st_unidade_regional",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlMunAtenPsico": [
        "co_unidade",
        "co_municipio",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEstabRegimeRes": [
        "co_unidade",
        "tp_modulo",
        "nu_vagas_existentes",
        "nu_vagas_sus",
        "dt_ativacao",
        "dt_desativacao",
        "co_profissional_sus",
        "co_cbo",
        "tp_sus_nao_sus",
        "ind_vinculacao",
        "co_cnes_caps_ref",
        "co_prof_sus_caps_ref",
        "co_cbo_caps_ref",
        "ind_vinculacao_caps_ref",
        "co_cnes_unid_basica_ref",
        "co_cnes_hosp_geral_ref",
        "st_unidade_regional",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlMunRegimeRes": [
        "co_unidade",
        "co_municipio",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEstabAvaliacao": [
        "co_unidade",
        "co_avaliacao",
        "co_classificacao",
        "to_chardt_avaliacaoddmmyyyy",
        "co_instituicao_avaliadora",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlAdmGerenciaCnes": [
        "nu_cnpj_adm",
        "co_unidade",
        "to_chardt_vigencia_inicialddmmyyyy",
        "to_chardt_vigencia_finalddmmyyyy",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEstabEqpUnidApoio": [
        "co_municipio",
        "co_area",
        "seq_equipe",
        "co_endereco_complementar",
        "co_unidade",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEstabEqpEmbarcacao": [
        "co_municipio",
        "co_area",
        "seq_equipe",
        "nu_embarcacao",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "tbEstabHorarioAtend": [
        "co_unidade",
        "co_dia_semana",
        "hr_inicio_atendimento",
        "hr_fim_atendimento",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEstabProfComissao": [
        "co_unidade",
        "co_comissao",
        "co_profissional_sus",
        "co_cbo",
        "tp_sus_nao_sus",
        "tp_vinculacao",
        "st_resp_tecnico",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "tbEstabAtivSecundaria": [
        "co_unidade",
        "co_atividade_secundaria",
        "to_chardt_atualizacaoddmmyyyy"
    ],
    "rlEquipeAldeia": [
        "co_municipio",
        "co_area",
        "co_seq_equipe",
        "co_aldeia",
        "co_unidade",
        "to_chardt_atualizacaoddmmyyyy"
    ]
}

CNES_DTYPES = {
    "rlEstabComplementar": {
        "co_unidade": "string",
        "co_leito": "category",
        "co_tipo_leito": "category",
        "qt_exist": "Int64",
        "qt_sus": "Int64",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "tbEstabelecimento": {
        "co_unidade": "string",
        "co_cnes": "string",
        "nu_cnpj_mantenedora": "string",
        "tp_pfpj": "category",
        "nivel_dep": "category",
        "co_cep": "string",
        "co_regiao_saude": "category",
        "co_clientela": "category",
        "tp_unidade": "category",
        "co_turno_atendimento": "category",
        "co_estado_gestor": "category",
        "co_municipio_gestor": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]",
        "co_motivo_desab": "category",
        "nu_latitude": "float64",
        "nu_longitude": "float64",
        "co_natureza_jur": "category",
        "tp_estab_sempre_aberto": "category",
        "st_conexao_internet": "category",
        "co_tipo_estabelecimento": "category",
        "co_atividade_principal": "category",
        "st_contrato_formalizado": "category",
        "tp_gestao": "category"
    },
    "tbMantenedora": {
        "nu_cnpj_mantenedora": "string",
        "co_banco": "category",
        "co_cep": "string",
        "co_municipio": "category",
        "co_regiao_saude": "category",
        "st_fms_fes": "category",
        "co_natureza_jur": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]",
        "co_gestor": "category",
        "co_municipio_mant": "category"
    },
    "rlEstabAtendPrestConv": {
        "co_unidade": "string",
        "co_atendimento_prestado": "category",
        "co_convenio": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEstabProgFundo": {
        "co_unidade": "string",
        "co_atividade": "category",
        "tp_estadual_municipal": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEstabColetaSelRejeito": {
        "co_unidade": "string",
        "co_coleta_rejeito": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEstabServicoApoio": {
        "co_unidade": "string",
        "co_servico_apoio": "category",
        "co_caracteristica": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "tbDialise": {
        "co_unidade": "string",
        "qt_sala_hbsag_pos": "Int64",
        "qt_sala_hbsag_neg": "Int64",
        "qt_sala_dpi": "Int64",
        "qt_sala_dpac": "Int64",
        "qt_sala_reag_pos": "Int64",
        "qt_sala_reag_neg": "Int64",
        "qt_sala_rehcv": "Int64",
        "nu_maqh_prop": "Int64",
        "nu_maqh_outr": "Int64",
        "tp_filtro_areia": "category",
        "tp_filtro_carvao": "category",
        "tp_abrandador": "category",
        "tp_deoinizador": "category",
        "tp_osmose_reversa": "category",
        "tp_outros_trat_agua": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "tbQuimioRadio": {
        "co_unidade": "string",
        "nu_salarsimu": "Int64",
        "nu_salarplan": "Int64",
        "nu_slararmfo": "Int64",
        "nu_slarconfm": "Int64",
        "nu_slarmolde": "Int64",
        "nu_slarbolcp": "Int64",
        "nu_slaqarmaz": "Int64",
        "nu_slaqprepa": "Int64",
        "nu_slaqcdura": "Int64",
        "nu_slaqldura": "Int64",
        "nu_slacpflul": "Int64",
        "qt_eqrsimula": "Int64",
        "qt_eqracell6": "Int64",
        "qt_eqr_6seme": "Int64",
        "qt_eqr_6come": "Int64",
        "qt_rortv1050": "Int64",
        "qt_rorv50150": "Int64",
        "qt_rov150500": "Int64",
        "qt_runidcoba": "Int64",
        "qt_eqrbrbaix": "Int64",
        "qt_eqrbrmedi": "Int64",
        "qt_eqrbralta": "Int64",
        "qt_eqrmonita": "Int64",
        "qt_eqrmoniti": "Int64",
        "qt_eqrsispln": "Int64",
        "qt_eqrdoscli": "Int64",
        "qt_eqrfonsel": "Int64",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEstabComissaoOutro": {
        "co_unidade": "string",
        "co_comissao": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEstabInstFisiAssist": {
        "co_unidade": "string",
        "co_instalacao": "category",
        "qt_instalacao": "Int64",
        "nu_leitos": "Int64",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "tbDadosProfissionalSus": {
        "co_profissional_sus": "string",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "tbServicoReferenciado": {
        "co_unidade": "string",
        "co_servico_referenciado": "category",
        "tp_servico_referenciado": "category",
        "co_cnpj": "string",
        "co_municipio": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEstabEquipamento": {
        "co_unidade": "string",
        "co_equipamento": "category",
        "co_tipo_equipamento": "category",
        "qt_existente": "Int64",
        "qt_uso": "Int64",
        "tp_sus": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "tbCargaHorariaSus": {
        "co_unidade": "string",
        "co_profissional_sus": "string",
        "co_cbo": "category",
        "tp_sus_nao_sus": "category",
        "ind_vinculacao": "category",
        "qt_carga_horaria_ambulatorial": "Int64",
        "qt_carga_hor_hosp_sus": "Int64",
        "qt_carga_horaria_outros": "Int64",
        "tp_preceptor": "category",
        "tp_residente": "category",
        "to_charadt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "tbHemoterapia": {
        "co_unidade": "string",
        "nu_srecepcad": "Int64",
        "nu_striaghmt": "Int64",
        "nu_striagcln": "Int64",
        "nu_scoleta": "Int64",
        "nu_saferese": "Int64",
        "nu_sprestoq": "Int64",
        "nu_sproces": "Int64",
        "nu_sestoque": "Int64",
        "nu_sdistrib": "Int64",
        "nu_sorologia": "Int64",
        "nu_simunohem": "Int64",
        "nu_spretranf": "Int64",
        "nu_shemostas": "Int64",
        "nu_scontrolq": "Int64",
        "nu_sbiomolec": "Int64",
        "nu_simunfen": "Int64",
        "nu_stransfus": "Int64",
        "nu_ssgdoador": "Int64",
        "qt_ecadrecli": "Int64",
        "qt_ecentrefr": "Int64",
        "qt_erfguasng": "Int64",
        "qt_econgrapd": "Int64",
        "qt_eextaplsm": "Int64",
        "qt_efreez18": "Int64",
        "qt_efreez30": "Int64",
        "qt_eagitplqt": "Int64",
        "qt_eseladora": "Int64",
        "qt_eirradhem": "Int64",
        "qt_eagltnosc": "Int64",
        "qt_emaqafres": "Int64",
        "qt_erfgareag": "Int64",
        "qt_erfgamsts": "Int64",
        "qt_ecapfllam": "Int64",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEstabServClass": {
        "co_unidade": "string",
        "co_servico": "category",
        "co_classificacao": "category",
        "tp_caracteristica": "category",
        "co_cnpjcpf": "string",
        "co_ambulatorial": "category",
        "co_ambulatorial_sus": "category",
        "co_hospitalar": "category",
        "co_hospitalar_sus": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlCooperativa": {
        "co_unidade": "string",
        "co_cooperativa": "string",
        "co_cbo": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "tbEquipe": {
        "co_municipio": "category",
        "co_area": "string",
        "seq_equipe": "string",
        "co_unidade": "string",
        "tp_equipe": "category",
        "dt_ativacao": "datetime64[ns]",
        "dt_desativacao": "datetime64[ns]",
        "tp_pop_assist_quilomb": "category",
        "tp_pop_assist_assent": "category",
        "tp_pop_assist_geral": "category",
        "tp_pop_assist_escola": "category",
        "tp_pop_assist_pronasci": "category",
        "tp_pop_assist_indigena": "category",
        "tp_pop_assist_ribeirinha": "category",
        "tp_pop_assist_situacao_rua": "category",
        "tp_pop_assist_priv_liberdade": "category",
        "tp_pop_assist_conflito_lei": "category",
        "tp_pop_assist_adol_conf_lei": "category",
        "cd_motivo_desativ": "category",
        "cd_tp_desativ": "category",
        "co_equipe": "string",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEstabEquipeProf": {
        "co_municipio": "category",
        "co_area": "string",
        "seq_equipe": "string",
        "co_profissional_sus": "string",
        "co_unidade": "string",
        "co_cbo": "category",
        "tp_sus_nao_sus": "category",
        "ind_vinculacao": "category",
        "co_microarea": "category",
        "dt_entrada": "datetime64[ns]",
        "dt_desligamento": "datetime64[ns]",
        "st_equipeminima": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "tbResidenciaMed": {
        "co_unidade": "string",
        "sq_residencia": "string",
        "co_municipio": "category",
        "co_cep": "string",
        "nu_cuidadores": "Int64",
        "nu_capacidade_masc": "Int64",
        "nu_capacidade_fem": "Int64",
        "tp_sus_nao_sus": "category",
        "dt_ativacao": "datetime64[ns]",
        "dt_desativacao": "datetime64[ns]",
        "st_parceria_ong": "category",
        "nu_cnpj_ong": "string",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "tbSegmento": {
        "co_municipio": "category",
        "co_segmento": "category",
        "tp_segmento": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "tbArea": {
        "co_municipio": "category",
        "co_area": "string",
        "cd_segmento": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEstabSipac": {
        "co_unidade": "string",
        "cod_sub_grupo_habilitacao": "category",
        "cmtp_inicio": "string",
        "cmtp_fim": "string",
        "nu_leitos": "Int64",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]",
        "tp_habilitacao": "category"
    },
    "tbProfResidencia": {
        "co_unidade": "string",
        "nu_residencia": "string",
        "co_profissional_sus": "string",
        "co_cbo": "category",
        "ind_vinculacao": "category",
        "tp_sus_nao_sus": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEstabSubTipo": {
        "co_unidade": "string",
        "co_tipo_unidade": "category",
        "co_sub_tipo_unidade": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEquipeNasfEsf": {
        "co_municipio": "category",
        "co_area": "string",
        "seq_equipe": "string",
        "co_municipio_esf": "category",
        "co_area_esf": "string",
        "seq_equipe_esf": "string",
        "nu_sequencial": "string",
        "co_unidade": "string",
        "tp_equipe_esf": "category",
        "co_cnes_esf": "string",
        "co_segmento_esf": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEstabPoloAldeia": {
        "co_unidade": "string",
        "co_aldeia": "category",
        "co_polobase": "category",
        "co_dsei": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEstabCentralReg": {
        "co_unidade": "string",
        "co_seq_central": "string",
        "co_subtipo_central": "category",
        "co_municipio_end": "category",
        "dt_ativacao": "datetime64[ns]",
        "dt_desativacao": "datetime64[ns]",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEstabSamu": {
        "co_unidade": "string",
        "dt_ativacao": "datetime64[ns]",
        "co_unidade_central": "string",
        "co_seq_central": "string",
        "co_prefixo_aeronave": "string",
        "nu_embarca_marinha": "string",
        "dt_desativacao": "datetime64[ns]",
        "co_desativacao": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEstabUnidAcolhim": {
        "co_unidade": "string",
        "sq_acolhimento": "string",
        "tp_acolhimento": "category",
        "co_municipio": "category",
        "co_cep": "string",
        "tp_estrutura": "category",
        "st_parceria_ong": "category",
        "nu_cnpj_ong": "string",
        "nu_vagas": "Int64",
        "co_profissional_sus": "string",
        "co_cbo": "category",
        "tp_sus_nao_sus": "category",
        "ind_vinculacao": "category",
        "dt_ativacao": "datetime64[ns]",
        "dt_desativacao": "datetime64[ns]",
        "st_unidade_regional": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlMunUnidAcolhim": {
        "co_unidade": "string",
        "co_municipio": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEstabAtenPsico": {
        "co_unidade": "string",
        "tp_estrutura": "category",
        "st_parceria_ong": "category",
        "nu_cnpj_ong": "string",
        "nu_vagas_acol_notur": "Int64",
        "co_profissional_sus": "string",
        "co_cbo": "category",
        "tp_sus_nao_sus": "category",
        "ind_vinculacao": "category",
        "co_cnes_referencia": "string",
        "st_unidade_regional": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlMunAtenPsico": {
        "co_unidade": "string",
        "co_municipio": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEstabRegimeRes": {
        "co_unidade": "string",
        "tp_modulo": "category",
        "nu_vagas_existentes": "Int64",
        "nu_vagas_sus": "Int64",
        "dt_ativacao": "datetime64[ns]",
        "dt_desativacao": "datetime64[ns]",
        "co_profissional_sus": "string",
        "co_cbo": "category",
        "tp_sus_nao_sus": "category",
        "ind_vinculacao": "category",
        "co_cnes_caps_ref": "string",
        "co_prof_sus_caps_ref": "string",
        "co_cbo_caps_ref": "category",
        "ind_vinculacao_caps_ref": "category",
        "co_cnes_unid_basica_ref": "string",
        "co_cnes_hosp_geral_ref": "string",
        "st_unidade_regional": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlMunRegimeRes": {
        "co_unidade": "string",
        "co_municipio": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEstabAvaliacao": {
        "co_unidade": "string",
        "co_avaliacao": "category",
        "co_classificacao": "category",
        "to_chardt_avaliacaoddmmyyyy": "datetime64[ns]",
        "co_instituicao_avaliadora": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlAdmGerenciaCnes": {
        "nu_cnpj_adm": "string",
        "co_unidade": "string",
        "to_chardt_vigencia_inicialddmmyyyy": "datetime64[ns]",
        "to_chardt_vigencia_finalddmmyyyy": "datetime64[ns]",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEstabEqpUnidApoio": {
        "co_municipio": "category",
        "co_area": "string",
        "seq_equipe": "string",
        "co_endereco_complementar": "string",
        "co_unidade": "string",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEstabEqpEmbarcacao": {
        "co_municipio": "category",
        "co_area": "string",
        "seq_equipe": "string",
        "nu_embarcacao": "string",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "tbEstabHorarioAtend": {
        "co_unidade": "string",
        "co_dia_semana": "category",
        "hr_inicio_atendimento": "string",
        "hr_fim_atendimento": "string",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEstabProfComissao": {
        "co_unidade": "string",
        "co_comissao": "category",
        "co_profissional_sus": "string",
        "co_cbo": "category",
        "tp_sus_nao_sus": "category",
        "tp_vinculacao": "category",
        "st_resp_tecnico": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "tbEstabAtivSecundaria": {
        "co_unidade": "string",
        "co_atividade_secundaria": "category",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    },
    "rlEquipeAldeia": {
        "co_municipio": "category",
        "co_area": "string",
        "co_seq_equipe": "string",
        "co_aldeia": "category",
        "co_unidade": "string",
        "to_chardt_atualizacaoddmmyyyy": "datetime64[ns]"
    }
}

# --- Mapeamento de Chaves a partir do Dicionário CNES 2025 ---
CNES_PKEY = {
    "rlEstabComplementar": "co_unidade",
    "tbEstabelecimento": "co_unidade",
    "tbMantenedora": "nu_cnpj_mantenedora",
    "rlEstabAtendPrestConv": "co_unidade",
    "rlEstabProgFundo": "co_unidade",
    "rlEstabColetaSelRejeito": "co_unidade",
    "rlEstabServicoApoio": "co_unidade",
    "tbDialise": "co_unidade",
    "tbQuimioRadio": "co_unidade",
    "rlEstabComissaoOutro": "co_unidade",
    "rlEstabInstFisiAssist": "co_unidade",
    "tbDadosProfissionalSus": "co_profissional_sus",
    "tbServicoReferenciado": "co_unidade",
    "rlEstabEquipamento": "co_unidade",
    "tbCargaHorariaSus": "co_unidade",
    "tbHemoterapia": "co_unidade",
    "rlEstabServClass": "co_unidade",
    "rlCooperativa": "co_unidade",
    "tbEquipe": "co_municipio",
    "rlEstabEquipeProf": "co_municipio",
    "tbResidenciaMed": "co_unidade",
    "tbSegmento": "co_municipio",
    "tbArea": "co_municipio",
    "tbEquipeChDifer": "co_municipio",
    "tbEquipeAtendCompl": "co_municipio",
    "rlEstabSipac": "co_unidade",
    "tbProfResidencia": "co_unidade",
    "rlEstabSubTipo": "co_unidade",
    "rlEstabEndCompl": "co_unidade",
    "tbEstabBanco": "co_unidade",
    "rlEquipeNasfEsf": "co_municipio",
    "rlEstabPoloAldeia": "co_unidade",
    "rlEstabRepresentante": "co_unidade",
    "rlJustifPtProf": "co_profissional_sus",
    "rlJustifPtProfLog": "co_profissional_sus",
    "rlEstabEquipeMun": "co_municipio",
    "rlEstabTeleCnes": "co_unidade",
    "rlEstabOrgParc": "co_unidade",
    "rlEstabCentralReg": "co_unidade",
    "rlEstabSamu": "co_unidade",
    "rlEstabUnidAcolhim": "co_unidade",
    "rlMunUnidAcolhim": "co_unidade",
    "rlEstabAtenPsico": "co_unidade",
    "rlMunAtenPsico": "co_unidade",
    "rlEstabRegimeRes": "co_unidade",
    "rlMunRegimeRes": "co_unidade",
    "rlEstabAvaliacao": "co_unidade",
    "rlAdmGerenciaCnes": "nu_cnpj_adm",
    "rlEstabEqpUnidApoio": "co_municipio",
    "rlEstabEqpEmbarcacao": "co_municipio",
    "tbJustificaDesligaPrf": "co_unidade",
    "tbEstabHorarioAtend": "co_unidade",
    "tbLocalGerenteAdministrador": "nu_cnpj_gerente_administrador",
    "rlEstabProfComissao": "co_unidade",
    "tbEstabAtivSecundaria": "co_unidade",
    "rlEquipeAldeia": "co_municipio"
}

CNES_FKEY = {
    "rlEstabComplementar": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabAtendPrestConv": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabProgFundo": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabColetaSelRejeito": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabServicoApoio": {
        "co_unidade": "tbEstabelecimento"
    },
    "tbDialise": {
        "co_unidade": "tbEstabelecimento"
    },
    "tbQuimioRadio": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabComissaoOutro": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabInstFisiAssist": {
        "co_unidade": "tbEstabelecimento"
    },
    "tbServicoReferenciado": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabEquipamento": {
        "co_unidade": "tbEstabelecimento"
    },
    "tbCargaHorariaSus": {
        "co_unidade": "tbEstabelecimento"
    },
    "tbHemoterapia": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabServClass": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlCooperativa": {
        "co_unidade": "tbEstabelecimento"
    },
    "tbEquipe": {
        "co_municipio": "tbArea",
        "co_area": "tbArea",
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabEquipeProf": {
        "co_municipio": "tbEquipe",
        "co_area": "tbEquipe",
        "seq_equipe": "tbEquipe",
        "co_profissional_sus": "tbCargaHorariaSus",
        "co_unidade": "tbCargaHorariaSus",
        "co_cbo": "tbCargaHorariaSus",
        "tp_sus_nao_sus": "tbCargaHorariaSus",
        "ind_vinc": "tbCargaHorariaSus"
    },
    "tbResidenciaMed": {
        "co_unidade": "tbEstabelecimento",
        "co_profissional_": "tbCargaHorariaSus",
        "co_cbo": "tbCargaHorariaSus",
        "tp_sus_nao_sus": "tbCargaHorariaSus",
        "ind_vinc": "tbCargaHorariaSus"
    },
    "tbArea": {
        "co_municipio": "tbSegmento",
        "cd_segmento": "tbSegmento"
    },
    "tbEquipeChDifer": {
        "co_municipio": "rlEstabEquipeProf",
        "co_area": "rlEstabEquipeProf",
        "seq_equipe": "rlEstabEquipeProf",
        "co_profissional_sus": "rlEstabEquipeProf"
    },
    "rlEstabSipac": {
        "co_unidade": "tbEstabelecimento"
    },
    "tbProfResidencia": {
        "co_unidade": "tbResidenciaMed",
        "nu_residencia": "tbResidenciaMed",
        "co_profissional_sus": "tbCargaHorariaSus",
        "co_cbo": "tbCargaHorariaSus",
        "ind_vinc": "tbCargaHorariaSus",
        "tp_sus_nao_sus": "tbCargaHorariaSus"
    },
    "rlEstabSubTipo": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabEndCompl": {
        "co_unidade": "tbEstabelecimento"
    },
    "tbEstabBanco": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlEquipeNasfEsf": {
        "co_municipio": "tbEquipe",
        "co_area": "tbEquipe",
        "seq_equipe": "tbEquipe",
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabPoloAldeia": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabRepresentante": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlJustifPtProf": {
        "co_profissional_sus": "tbCargaHorariaSus",
        "co_unidade": "tbEstabelecimento"
    },
    "rlJustifPtProfLog": {
        "co_profissional_sus": "tbCargaHorariaSus",
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabEquipeMun": {
        "co_municipio": "tbEquipe",
        "co_area": "tbEquipe",
        "seq_equipe": "tbEquipe"
    },
    "rlEstabTeleCnes": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabOrgParc": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabCentralReg": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabSamu": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabUnidAcolhim": {
        "co_unidade": "tbEstabelecimento",
        "co_profissional": "tbCargaHorariaSus",
        "co_cbo": "tbCargaHorariaSus",
        "tp_sus_nao_sus": "tbCargaHorariaSus"
    },
    "rlMunUnidAcolhim": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabAtenPsico": {
        "co_unidade": "tbEstabelecimento",
        "co_profissional_sus": "tbCargaHorariaSus",
        "co_cbo": "tbCargaHorariaSus",
        "tp_sus_nao_sus": "tbCargaHorariaSus"
    },
    "rlMunAtenPsico": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabRegimeRes": {
        "co_unidade": "tbEstabelecimento",
        "co_profissional_sus": "tbCargaHorariaSus",
        "co_cbo": "tbCargaHorariaSus",
        "tp_sus_nao_sus": "tbCargaHorariaSus",
        "co_prof_sus_caps_ref": "tbCargaHorariaSus",
        "co_cbo_caps_ref": "tbCargaHorariaSus",
        "tp_sus_nao_sus_caps_ref": "tbCargaHorariaSus"
    },
    "rlMunRegimeRes": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabAvaliacao": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlAdmGerenciaCnes": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabEqpUnidApoio": {
        "co_municipio": "tbEquipe",
        "co_area": "tbEquipe",
        "seq_equipe": "tbEquipe",
        "co_endereco_complementar": "rlEstabEndCompl",
        "co_unidade": "rlEstabEndCompl"
    },
    "rlEstabEqpEmbarcacao": {
        "co_municipio": "tbEquipe",
        "co_area": "tbEquipe",
        "seq_equipe": "tbEquipe"
    },
    "tbJustificaDesligaPrf": {
        "co_unidade": "tbEstabelecimento"
    },
    "tbEstabHorarioAtend": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlEstabProfComissao": {
        "co_unidade": "tbEstabelecimento"
    },
    "tbEstabAtivSecundaria": {
        "co_unidade": "tbEstabelecimento"
    },
    "rlEquipeAldeia": {
        "co_municipio": "tbEquipe",
        "co_area": "tbEquipe",
        "co_seq_equipe": "tbEquipe",
        "co_unidade": "tbEstabelecimento"
    },
    "tbEquipeAtendCompl": {
        "co_municipio": "rlEstabEquipeProf",
        "co_area": "rlEstabEquipeProf",
        "seq_equipe": "rlEstabEquipeProf",
        "co_profissional_sus": "rlEstabEquipeProf"
    }
}
