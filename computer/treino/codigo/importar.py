"""
Importa videos/fotos gravados FORA do gravador (celular, outra camera) pras
mesmas pastas que o gravador usa -- depois e so rodar o treino.

  letra ou NADA -> computer/treino/gravacoes/letras/<LETRA>/
  palavra       -> computer/treino/gravacoes/palavras/<PALAVRA>/

Uso, dentro de computer/:

  # 1) pasta com uma subpasta por letra/palavra (o nome da subpasta manda)
  .venv\\Scripts\\python treino\\codigo\\importar.py "D:\\DCIM\\VisuAll"

  # 2) todos os arquivos de uma pasta sao da mesma letra/palavra
  .venv\\Scripts\\python treino\\codigo\\importar.py "D:\\DCIM\\Camera" --rotulo H

  # 3) celular Android no cabo (precisa do adb), pasta /sdcard/DCIM/VisuAll
  .venv\\Scripts\\python treino\\codigo\\importar.py --adb

Exemplo da origem no caso 1:

  VisuAll/
    H/       video1.mp4  video2.mp4
    D/       foto1.jpg   video3.mp4   (letra parada aceita foto ou video)
    OBRIGADO/  video4.mp4             (nome que nao e letra = palavra)

Os arquivos sao COPIADOS (a origem fica como estava, a nao ser com --mover)
e ganham nome de data/hora; rodar duas vezes na mesma origem duplica.
"""
import argparse
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parent))
import comum  # noqa: E402
import pontos  # noqa: E402

# O OpenCV do treino abre estes direto; os outros sao regravados em .mp4.
EXT_VIDEO_DIRETO = {".mp4", ".mov"}
PASTA_ADB = "/sdcard/DCIM/VisuAll"


def carimbo():
    # Sem "_" antes dos milissegundos: AAAAMMDD_HHMMSS_NN e o formato de
    # rajada de fotos (pontos.id_da_gravacao), e cada arquivo importado e uma
    # gravacao so.
    return datetime.now().strftime("%Y%m%d_%H%M%S%f")[:-3]


def regrava_mp4(origem, destino):
    """Copia quadro a quadro pra um .mp4 que o OpenCV do treino abre."""
    cap = cv2.VideoCapture(str(origem))
    ok, quadro = cap.read()
    if not ok:
        cap.release()
        return False
    altura, largura = quadro.shape[:2]
    escritor = cv2.VideoWriter(str(destino), cv2.VideoWriter_fourcc(*"mp4v"),
                               cap.get(cv2.CAP_PROP_FPS) or 30.0, (largura, altura))
    while ok:
        escritor.write(quadro)
        ok, quadro = cap.read()
    escritor.release()
    cap.release()
    return True


def destino_de(rotulo):
    """(tipo, rotulo) de uma subpasta: letra/NADA vai pra letras, o resto e palavra."""
    rotulo = comum.nome_de_palavra(rotulo)
    if rotulo in comum.alfabeto() or rotulo == comum.NADA:
        return "letras", rotulo
    return "palavras", rotulo


def importa(arquivo, rotulo, mover, relatorio):
    tipo, rotulo = destino_de(rotulo)
    ext = arquivo.suffix.lower()
    pasta = comum.GRAVACOES / tipo / rotulo
    eh_foto = ext in pontos.EXT_FOTO
    if eh_foto and (tipo == "palavras" or comum.eh_dinamica(rotulo)):
        relatorio["ignorados"].append("%s: %s precisa de video, nao de foto" % (arquivo.name, rotulo))
        return
    if not eh_foto and ext not in pontos.EXT_VIDEO:
        relatorio["ignorados"].append("%s: tipo de arquivo %s nao suportado" % (arquivo.name, ext))
        return

    pasta.mkdir(parents=True, exist_ok=True)
    if eh_foto or ext in EXT_VIDEO_DIRETO:
        destino = pasta / (carimbo() + ext)
        (shutil.move if mover else shutil.copy2)(str(arquivo), str(destino))
    else:
        destino = pasta / (carimbo() + ".mp4")
        if not regrava_mp4(arquivo, destino):
            relatorio["ignorados"].append("%s: nao consegui abrir o video" % arquivo.name)
            return
        if mover:
            arquivo.unlink()
    relatorio["por_rotulo"][(tipo, rotulo)] = relatorio["por_rotulo"].get((tipo, rotulo), 0) + 1


def puxa_do_celular():
    destino = Path(tempfile.mkdtemp(prefix="visuall_adb_"))
    print("Puxando %s do celular via adb..." % PASTA_ADB)
    r = subprocess.run(["adb", "pull", PASTA_ADB, str(destino)], capture_output=True, text=True)
    if r.returncode != 0:
        print("ERRO no adb pull:\n" + (r.stderr or r.stdout))
        print("Confira: celular conectado, depuracao USB ligada e a pasta %s existe." % PASTA_ADB)
        return None
    interna = destino / Path(PASTA_ADB).name
    return interna if interna.exists() else destino


def main():
    ap = argparse.ArgumentParser(description="Importa gravacoes de fora do gravador.")
    ap.add_argument("origem", nargs="?", help="pasta com uma subpasta por letra/palavra")
    ap.add_argument("--adb", action="store_true", help="puxa %s do celular" % PASTA_ADB)
    ap.add_argument("--rotulo", help="todos os arquivos da origem sao desta letra/palavra")
    ap.add_argument("--mover", action="store_true", help="move em vez de copiar")
    args = ap.parse_args()

    if args.adb:
        origem = puxa_do_celular()
        if origem is None:
            return 1
    elif args.origem and Path(args.origem).is_dir():
        origem = Path(args.origem)
    else:
        ap.print_help()
        return 1

    relatorio = {"por_rotulo": {}, "ignorados": []}
    if args.rotulo:
        grupos = [(args.rotulo, origem)]
    else:
        grupos = [(p.name, p) for p in sorted(origem.iterdir()) if p.is_dir()]
        if not grupos:
            print("ERRO: '%s' nao tem subpastas. Use --rotulo H se tudo for da mesma letra." % origem)
            return 1
    for rotulo, pasta in grupos:
        for arquivo in sorted(pasta.iterdir()):
            if arquivo.is_file():
                importa(arquivo, rotulo, args.mover, relatorio)

    print("\nImportado:")
    for (tipo, rotulo), n in sorted(relatorio["por_rotulo"].items()):
        print("  %-9s %-14s %d arquivo(s)" % (tipo, rotulo, n))
    if not relatorio["por_rotulo"]:
        print("  nada")
    if relatorio["ignorados"]:
        print("\nIgnorados:")
        for linha in relatorio["ignorados"]:
            print("  " + linha)
    print("\nProximo passo: '2 - Retreinar palavras.bat' ou '3 - Retreinar letras.bat'")
    print("(feche a camera com Q e responda S pra treinar).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
