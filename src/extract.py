from pathlib import Path
import requests
from requests.exceptions import RequestException
from typing import List
from tqdm import tqdm
from src.paths import RAW_FOLDER

BASE_URL = "https://cnes.datasus.gov.br/EstatisticasServlet?path=BASE_DE_DADOS_CNES_"

def download_cnes_zips(
        periods : List[str], 
        output_folder : Path = RAW_FOLDER,
        reprocess : bool = True,
        block_size : int = 16 * 1024
) -> None:
    """
    Baixa arquivos ZIP do CNES para os períodos informados (YYYYMM).
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

            try:
                response = session.get(file_url, stream=True, timeout=30)
                response.raise_for_status()
            
                total_size = int(response.headers.get('content-length', 0))
                
                with open(file_path, "wb") as f, tqdm(
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
                    print(f"[AVISO] Download incompleto de {file_name}, removendo arquivo.")
                    file_path.unlink(missing_ok=True)
                    
            except RequestException as e:
                print(f"[ERRO] Falha ao baixar {file_name}: {e}")
                continue

if __name__ == "__main__":
    download_cnes_zips(["201701"])