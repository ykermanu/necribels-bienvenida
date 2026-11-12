"""Arma el paquete de recursos de la bienvenida de Ñecribels con TODAS las imagenes de la carpeta imagenes/.
Cada imagen queda como un «caracter» de la fuente necribels:bienvenida; Proto los va rotando al entrar alguien.
Los GIF (y WebP animados) se guardan cuadro por cuadro y Proto los reproduce como animacion.
salida/pack.zip  -> lo descarga Minecraft (enlace en server.properties)
salida/lista.json -> lo lee Proto para saber que caracter es cada imagen
Lo corre GitHub solo (Actions) cada vez que se suben o borran imagenes. No hay que tocarlo."""
import io, json, zipfile, pathlib
from PIL import Image

ALTO = 24          # alto de la imagen en el titulo (Minecraft lo multiplica x4 en pantalla)
SOBRE_LINEA = 20   # cuanto sube la imagen sobre el texto
MAX_PX = 256       # las fotos grandes se achican a esto (lado mayor) para que el paquete pese poco
MAX_PX_GIF = 160   # cada cuadro de un GIF (son muchos: mas chicos)
MAX_CUADROS = 40   # un GIF con mas cuadros se reparte en 40 (saltando cuadros, sin cambiar la duracion total)
FORMATO = 34       # paquete de recursos para Minecraft 1.21.1
R = pathlib.Path(__file__).resolve().parent.parent
IMG, SAL = R / "imagenes", R / "salida"
EXT = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}

SAL.mkdir(exist_ok=True)
previa = {}
try:
    for x in json.loads((SAL / "lista.json").read_text(encoding="utf-8"))["imagenes"]:
        previa[x["archivo"]] = x["caracter"]
        for k, c in enumerate(x.get("cuadros", [])[1:], 1):
            previa[f"{x['archivo']}#{k}"] = c
except Exception:
    pass
archivos = sorted(p for p in IMG.glob("*") if p.suffix.lower() in EXT) if IMG.exists() else []
usados = {c for a, c in previa.items() if any(p.name == a.split("#")[0] for p in archivos)}
inicio = max([ord(c) + 1 for c in previa.values()] + [0xE000])      # las nuevas nunca reusan un caracter viejo
libre = (chr(i) for i in list(range(inicio, 0xF8FF)) + list(range(0xE000, inicio)))
lista, providers, texturas = [], [], {}
def nuevo_caracter(nombre_clave):
    car = previa.get(nombre_clave) if previa.get(nombre_clave) in usados else None
    while car is None:
        c = next(libre)
        if c not in usados:
            car = c
    usados.add(car)
    return car


def cuadros(p):
    """[(imagen RGBA, ms)] de la imagen; una sola si no es animada."""
    im = Image.open(p)
    n = getattr(im, "n_frames", 1)
    if n <= 1:
        im.seek(0)
        x = im.convert("RGBA"); x.thumbnail((MAX_PX, MAX_PX), Image.LANCZOS)
        return [(x, 0)]
    todos = []
    for i in range(n):
        im.seek(i)
        x = im.convert("RGBA"); x.thumbnail((MAX_PX_GIF, MAX_PX_GIF), Image.LANCZOS)
        todos.append((x, max(20, int(im.info.get("duration") or 100))))
    if len(todos) > MAX_CUADROS:                           # se saltan cuadros; cada uno dura lo de los saltados
        paso = len(todos) / MAX_CUADROS
        grupos = [todos[int(i * paso):int((i + 1) * paso)] for i in range(MAX_CUADROS)]
        todos = [(g[0][0], sum(ms for _, ms in g)) for g in grupos if g]
    return todos


for p in archivos:
    try:
        cs = cuadros(p)
    except Exception as e:
        print(f"saltada {p.name}: no es una imagen valida ({e})")
        continue
    cars, durs = [], []
    for k, (im, ms) in enumerate(cs):
        car = nuevo_caracter(p.name if k == 0 else f"{p.name}#{k}")
        nombre = f"img_{ord(car):04x}.png"
        b = io.BytesIO(); im.save(b, "PNG", optimize=True); texturas[nombre] = b.getvalue()
        providers.append({"type": "bitmap", "file": f"necribels:font/{nombre}", "height": ALTO, "ascent": SOBRE_LINEA, "chars": [car]})
        cars.append(car); durs.append(ms)
    e = {"archivo": p.name, "caracter": cars[0], "ancho": cs[0][0].width, "alto": cs[0][0].height}
    if len(cars) > 1:
        e.update(animada=True, cuadros=cars, duraciones_ms=durs)
    lista.append(e)
    print(f"ok {p.name} -> U+{ord(cars[0]):04X}" + (f" ({len(cars)} cuadros, {sum(durs) / 1000:.1f} s)" if len(cars) > 1 else f" ({e['ancho']}x{e['alto']})"))

mcmeta = {"pack": {"pack_format": FORMATO, "description": "Bienvenida de Ñecribels"}}
z = io.BytesIO()
with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
    def poner(ruta, datos):
        info = zipfile.ZipInfo(ruta, date_time=(2026, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
        zf.writestr(info, datos)
    poner("pack.mcmeta", json.dumps(mcmeta, ensure_ascii=False, indent=1))
    poner("assets/necribels/font/bienvenida.json", json.dumps({"providers": providers}, ensure_ascii=False, indent=1))
    for n, d in sorted(texturas.items()):
        poner(f"assets/necribels/textures/font/{n}", d)
(SAL / "pack.zip").write_bytes(z.getvalue())
import hashlib
(SAL / "lista.json").write_text(json.dumps({"fuente": "necribels:bienvenida", "sha1": hashlib.sha1(z.getvalue()).hexdigest(),
                                            "imagenes": lista}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"{len(lista)} imagenes, paquete de {len(z.getvalue()) // 1024} KB")
