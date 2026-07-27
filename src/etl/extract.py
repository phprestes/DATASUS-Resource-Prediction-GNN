from pathlib import Path
import zipfile
import requests
from requests.exceptions import RequestException
from typing import List
from tqdm import tqdm
from src.config.paths import RAW_FOLDER

BASE_URL = "https://cnes.datasus.gov.br/EstatisticasServlet?path=BASE_DE_DADOS_CNES_"

# Amostra temporal canônica do projeto: janeiro de cada ano, 2017 a 2026.
# Dez snapshots, nove transições. Ver docs/03-decisoes.md, D-04 — o projeto
# original previa cinco snapshots bienais, que produzem apenas quatro
# transições e não sustentam afirmação sobre dinâmica temporal — e D-29, que
# acrescentou 202601.
#
# O ano final é aberto de propósito: `ANO_FINAL` é o último janeiro publicado
# pelo CNES, e passar de um ano para o seguinte é editar uma constante. Nada no
# resto do código conta snapshots à mão; quem precisa da lista real usa
# `changes.periodos_disponiveis()`, que olha a camada primária.
ANO_INICIAL = 2017
ANO_FINAL = 2026
PERIODOS_ANUAIS: List[str] = [f"{ano}01" for ano in range(ANO_INICIAL, ANO_FINAL + 1)]

def download_cnes_zips(
        periods : List[str],
        output_folder : Path = RAW_FOLDER,
        reprocess : bool = False,
        block_size : int = 16 * 1024
) -> None:
    """
    Baixa arquivos ZIP do CNES para os períodos informados (YYYYMM).

    `reprocess=False` pula o que já existe em disco. É o default porque cada ZIP
    tem centenas de megabytes e a série inteira são vários gigabytes: rebaixar
    por acidente é caro. Os três estágios do ETL usam o mesmo default.

    Args:
        periods: competências `YYYYMM` a baixar.
        output_folder: destino, a camada 01.
        reprocess: rebaixa o que já existe em disco.
        block_size: tamanho do bloco de streaming, em bytes.

    Returns:
        Nada. O efeito é o arquivo em disco.
    """
    output_folder.mkdir(parents=True, exist_ok=True)

    with requests.Session() as session:
        for periodo in periods:
            file_url = f"{BASE_URL}{periodo}.ZIP"
            file_name = file_url.split('path=')[-1]
            file_path = output_folder / file_name

            if file_path.exists() and not reprocess:
                print(f"{file_name} já existe. Pulando...")
                continue

            print(f"Baixando {file_name}...")

            # Baixa para um nome temporário e só renomeia ao concluir. Sem isso,
            # um arquivo parcial ocupa o nome final e passa por completo para
            # qualquer outro processo — foi assim que uma execução do ETL
            # concorrente ao download leu um ZIP truncado como se estivesse
            # pronto. O rename é atômico no mesmo sistema de arquivos.
            parcial = file_path.with_suffix(".ZIP.parcial")

            try:
                response = session.get(file_url, stream=True, timeout=30)
                response.raise_for_status()

                total_size = int(response.headers.get('content-length', 0))

                with open(parcial, "wb") as f, tqdm(
                    total=total_size,
                    unit='iB',
                    unit_scale=True,
                    desc=f"Baixando {file_name}",
                ) as progress_bar:
                    for chunk in response.iter_content(block_size):
                        if chunk:
                            f.write(chunk)
                            progress_bar.update(len(chunk))

                if total_size and progress_bar.n != total_size:
                    print(f"[AVISO] Download incompleto de {file_name}, descartando.")
                    parcial.unlink(missing_ok=True)
                    continue

                # O servidor do CNES não manda content-length, então o tamanho
                # esperado não é verificável. A checagem que resta é o ZIP abrir:
                # um truncamento sobrevive ao download mas não ao teste.
                if not zipfile.is_zipfile(parcial):
                    print(f"[ERRO] {file_name} não é um ZIP válido, descartando.")
                    parcial.unlink(missing_ok=True)
                    continue

                parcial.replace(file_path)

            except RequestException as e:
                print(f"[ERRO] Falha ao baixar {file_name}: {e}")
                parcial.unlink(missing_ok=True)
                continue

if __name__ == "__main__":
    import sys

    periodos = sys.argv[1:] or PERIODOS_ANUAIS
    print(f"Baixando {len(periodos)} competências: {periodos}")
    download_cnes_zips(periodos)