"""Registro de fuentes de informacion, deliberadamente diverso en naturaleza institucional
para mitigar sesgo ideologico/de mercado (requisito 1).

Cada fuente declara su `institution_type`, usado despues por el motor de consenso para exigir
diversidad institucional antes de aceptar un evento (ver crosscheck/reliability.py).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

InstitutionType = Literal[
    "banco_central",        # comunicados oficiales de politica monetaria
    "agencia_prensa",       # agencias de noticias globales
    "think_tank",           # analisis geopolitico/economico independiente, formato ensayo
    "organismo_multilateral",  # FMI, Banco Mundial, etc.
    "dato_primario",        # series estadisticas oficiales
    "defensa_seguridad",    # analisis especializado en conflicto armado y defensa
]


@dataclass(frozen=True)
class SourceConfig:
    name: str
    url: str
    institution_type: InstitutionType
    reliability_weight: float  # 0-1, ponderacion base (ver crosscheck/reliability.py)
    fetch_method: Literal["rss"] = "rss"


def _google_news_proxy(domain: str, window: str = "7d") -> str:
    """Construye una URL de busqueda RSS de Google News filtrada por dominio.

    Varias instituciones (Reuters, FMI, Banco Mundial, CFR, Brookings, Chatham House) han
    discontinuado su RSS publico directo o lo protegen con deteccion de bots (403 incluso con
    un User-Agent de navegador real). Este proxy es un servicio publico legitimo de agregacion
    de noticias -no una tecnica de evasion de esa proteccion-, y devuelve XML valido que
    `feedparser` procesa igual que cualquier otro feed. Limitacion conocida: el `link` de cada
    entrada apunta a un redirect de news.google.com en vez de a la URL directa del articulo."""
    return (
        f"https://news.google.com/rss/search?q=site:{domain}+when:{window}"
        "&hl=en-US&gl=US&ceid=US:en"
    )


SOURCES: list[SourceConfig] = [
    # --- Bancos centrales: comunicados oficiales (fuente primaria de politica monetaria) ---
    SourceConfig(
        "Federal Reserve - Press Releases",
        "https://www.federalreserve.gov/feeds/press_all.xml",
        "banco_central", 0.98,
    ),
    SourceConfig(
        "European Central Bank - Press",
        "https://www.ecb.europa.eu/rss/press.xml",
        "banco_central", 0.98,
    ),
    SourceConfig(
        "Bank of Japan - What's New",
        "https://www.boj.or.jp/en/rss/whatsnew.xml",
        "banco_central", 0.95,
    ),
    SourceConfig(
        "Bank of England - News",
        "https://www.bankofengland.co.uk/rss/news",
        "banco_central", 0.95,
    ),
    SourceConfig(
        "Bank of Canada - Press Releases",
        "https://www.bankofcanada.ca/content_type/press-releases/feed/",
        "banco_central", 0.92,
    ),
    # RBA y SNB bloquean RSS directo (403/404 verificados); via proxy de Google News.
    SourceConfig(
        "Reserve Bank of Australia",
        _google_news_proxy("rba.gov.au", window="14d"),
        "banco_central", 0.9,
    ),
    SourceConfig(
        "Swiss National Bank",
        _google_news_proxy("snb.ch", window="14d"),
        "banco_central", 0.9,
    ),
    # Reserve Bank of India y Banxico no publican RSS directo (verificado); via Google News.
    # El Banco Popular de China (PBOC) se investigo tambien -- su feed via proxy solo devuelve
    # 1 entrada util, demasiado debil para ser fiable como fuente; se deja fuera a proposito en
    # vez de anadir una entrada que en la practica nunca aportaria cobertura real.
    SourceConfig(
        "Reserve Bank of India",
        _google_news_proxy("rbi.org.in", window="14d"),
        "banco_central", 0.85,
    ),
    SourceConfig(
        "Banco de Mexico",
        _google_news_proxy("banxico.org.mx", window="14d"),
        "banco_central", 0.85,
    ),
    SourceConfig(
        "Monetary Authority of Singapore",
        _google_news_proxy("mas.gov.sg", window="14d"),
        "banco_central", 0.85,
    ),
    SourceConfig(
        "South African Reserve Bank",
        _google_news_proxy("resbank.co.za", window="14d"),
        "banco_central", 0.8,
    ),
    # Banco Central de Rusia (CBR): fuente primaria de politica monetaria igual que cualquier
    # otro banco central de la lista -- no lleva penalizacion especial de fiabilidad por ser
    # comunicado oficial de un estado (eso es cierto de TODOS los bancos centrales aqui). El
    # sesgo editorial de estado se marca explicitamente mas abajo en agencias de PRENSA
    # (TASS, Xinhua, Anadolu), que si compiten con Reuters/AP/AFP contando la misma noticia
    # desde angulos distintos -- ahi si importa la distincion.
    SourceConfig(
        "Central Bank of Russia",
        _google_news_proxy("cbr.ru", window="14d"),
        "banco_central", 0.85,
    ),
    # Se investigaron tambien Banco Central de Brasil, Bank of Korea y Banco Central de Turquia
    # -- los tres devuelven 1-2 entradas utiles via proxy, demasiado debil para ser fiables.
    # Se dejan fuera a proposito, igual que PBOC antes.

    # --- Organismos multilaterales (perspectiva supranacional, no ligada a un solo gobierno) ---
    # El RSS directo del FMI devuelve 403 (proteccion anti-bot) y el del Banco Mundial dejo de
    # servir XML real (redirige a HTML pese al parametro format=rss); se usa el proxy de
    # Google News, verificado activo (ver investigacion en README).
    SourceConfig(
        "IMF - News",
        _google_news_proxy("imf.org", window="3d"),
        "organismo_multilateral", 0.9,
    ),
    SourceConfig(
        "World Bank - News",
        _google_news_proxy("worldbank.org", window="3d"),
        "organismo_multilateral", 0.85,
    ),
    # BIS es el organismo que coordina a los propios bancos centrales (estabilidad financiera
    # global) -- mas autoridad todavia que un banco central individual en temas transfronterizos.
    # RSS directo de BIS y OCDE devuelven 404 (verificado); via Google News.
    SourceConfig(
        "BIS - Bank for International Settlements",
        _google_news_proxy("bis.org", window="14d"),
        "organismo_multilateral", 0.95,
    ),
    SourceConfig(
        "OECD",
        _google_news_proxy("oecd.org", window="7d"),
        "organismo_multilateral", 0.85,
    ),

    # --- Datos primarios: series estadisticas oficiales, no interpretacion -- categoria
    #     definida en InstitutionType pero sin ninguna fuente real hasta ahora. RSS directo de
    #     BLS y Eurostat devuelven 403/404 (verificado); via Google News. ---
    SourceConfig(
        "U.S. Bureau of Labor Statistics",
        _google_news_proxy("bls.gov", window="7d"),
        "dato_primario", 0.95,
    ),
    SourceConfig(
        "Eurostat",
        _google_news_proxy("ec.europa.eu/eurostat", window="7d"),
        "dato_primario", 0.9,
    ),
    # IEA (Agencia Internacional de la Energia): dato primario de energia directamente
    # relevante para analysis/risk_score.py:compute_energy_risk_by_country -- era un hueco
    # real que no deberia tener esta herramienta en concreto. RSS directo 404; via proxy.
    SourceConfig(
        "IEA - International Energy Agency",
        _google_news_proxy("iea.org", window="14d"),
        "dato_primario", 0.9,
    ),
    # ACLED (Armed Conflict Location & Event Data) es EL estandar de facto de datos de eventos
    # de conflicto a nivel de evento individual -- lo usan la ONU, bancos de desarrollo y la
    # academia como fuente primaria. Directamente relevante para el analisis de conflicto que
    # motiva esta expansion. RSS directo devuelve 404 (verificado); via Google News.
    SourceConfig(
        "ACLED - Armed Conflict Location & Event Data",
        _google_news_proxy("acleddata.com", window="14d"),
        "dato_primario", 0.95,
    ),
    # Se investigo tambien la FAO (seguridad alimentaria, muy ligada a hambruna por conflicto)
    # -- el proxy de Google News solo devuelve ofertas de empleo indexadas en fao.org, no
    # noticias reales. Se descarta: pasar el test HTTP no basta si el contenido es basura.

    # --- Datos humanitarios y de desplazamiento: la escala de una crisis humanitaria (personas
    #     desplazadas, necesidades no cubiertas) es una senal de severidad de conflicto tan
    #     directa como el propio registro de bajas -- ver persistence/conflicts.py. ---
    SourceConfig(
        "ReliefWeb (OCHA)",
        "https://reliefweb.int/updates/rss.xml",
        "organismo_multilateral", 0.9,
    ),
    SourceConfig(
        "UNHCR - Refugiados y desplazamiento",
        _google_news_proxy("unhcr.org", window="7d"),
        "organismo_multilateral", 0.85,
    ),

    # --- Agencias de prensa globales: se eligen deliberadamente con distinta procedencia
    #     geografica/editorial para evitar el sesgo de una unica sala de redaccion ---
    # El feed editorial publico de Reuters fue discontinuado (404); se usa el proxy de
    # Google News filtrado por dominio.
    SourceConfig(
        "Reuters - World News",
        _google_news_proxy("reuters.com", window="1d"),
        "agencia_prensa", 0.9,
    ),
    SourceConfig(
        "BBC - World",
        "http://feeds.bbci.co.uk/news/world/rss.xml",
        "agencia_prensa", 0.8,
    ),
    SourceConfig(
        "Al Jazeera - All",
        "https://www.aljazeera.com/xml/rss/all.xml",
        "agencia_prensa", 0.7,
    ),
    # AP y AFP son, junto con Reuters, las tres grandes agencias de noticias que alimentan a
    # la mayoria del resto de medios del mundo -- clave para el consenso cruzado, porque
    # cuando una historia sale de aqui, decenas de medios la republican con redaccion casi
    # identica (el emparejamiento de titulares en crosscheck/clustering.py las detecta bien).
    # Ninguna de las dos ofrece RSS publico directo ya (descontinuado, verificado); via proxy.
    SourceConfig(
        "Associated Press (AP)",
        _google_news_proxy("apnews.com", window="1d"),
        "agencia_prensa", 0.9,
    ),
    SourceConfig(
        "Agence France-Presse (AFP)",
        _google_news_proxy("afp.com", window="2d"),
        "agencia_prensa", 0.85,
    ),
    SourceConfig(
        "Deutsche Welle - All",
        "https://rss.dw.com/xml/rss-en-all",
        "agencia_prensa", 0.75,
    ),
    # Agencias regionales asiaticas -- editorialmente independientes (no son organos de
    # gobierno), anaden angulo de Asia Oriental infrarrepresentado en la lista original.
    SourceConfig(
        "Kyodo News (Japon)",
        _google_news_proxy("kyodonews.net", window="1d"),
        "agencia_prensa", 0.85,
    ),
    SourceConfig(
        "Yonhap (Corea del Sur)",
        _google_news_proxy("yna.co.kr", window="1d"),
        "agencia_prensa", 0.75,
    ),
    # AVISO EXPLICITO DE SESGO: TASS, Xinhua y Anadolu son agencias de prensa CONTROLADAS o
    # afiliadas al estado (Rusia, China y Turquia respectivamente) -- a diferencia de un banco
    # central (que es oficial por naturaleza en cualquier pais), aqui SI compiten en el mismo
    # rol informativo que Reuters/AP/AFP/BBC, y su cobertura de un conflicto puede reflejar la
    # posicion oficial de su gobierno mas que un reporteo independiente. Se incluyen a proposito
    # -no para tratarlas como equivalentes a una agencia independiente, sino porque ver COMO
    # cada gobierno enmarca un conflicto es en si mismo una senal geopolitica relevante para
    # esta herramienta-, con `reliability_weight` notablemente mas bajo para que el motor de
    # consenso (crosscheck/consensus.py) las pondere en consecuencia.
    SourceConfig(
        "TASS (Rusia, medio estatal)",
        _google_news_proxy("tass.com", window="1d"),
        "agencia_prensa", 0.5,
    ),
    SourceConfig(
        "Xinhua (China, medio estatal)",
        _google_news_proxy("news.cn", window="1d"),
        "agencia_prensa", 0.5,
    ),
    SourceConfig(
        "Anadolu Agency (Turquia, afiliada al estado)",
        _google_news_proxy("aa.com.tr", window="1d"),
        "agencia_prensa", 0.65,
    ),

    # --- Think tanks geopoliticos: aportan interpretacion experta y, al combinar varios de
    #     distinto perfil, se cancelan parcialmente sus sesgos individuales ---
    # CFR ya no publica RSS propio (404) y Chatham House bloquea con 403 (misma proteccion
    # anti-bot que el FMI, no se intenta sortear); ambos via proxy de Google News.
    SourceConfig(
        "Council on Foreign Relations",
        _google_news_proxy("cfr.org", window="7d"),
        "think_tank", 0.75,
    ),
    SourceConfig(
        "Brookings - Up Front",
        _google_news_proxy("brookings.edu", window="7d"),
        "think_tank", 0.75,
    ),
    SourceConfig(
        "Chatham House - Publications",
        _google_news_proxy("chathamhouse.org", window="7d"),
        "think_tank", 0.75,
    ),
    SourceConfig(
        "RAND Corporation",
        "https://www.rand.org/content/rand/blog.xml",
        "think_tank", 0.85,
    ),
    SourceConfig(
        "International Crisis Group",
        "https://www.crisisgroup.org/rss.xml",
        "think_tank", 0.85,
    ),
    SourceConfig(
        "Atlantic Council",
        "https://www.atlanticcouncil.org/feed/",
        "think_tank", 0.75,
    ),
    SourceConfig(
        "CSIS - Center for Strategic and International Studies",
        "https://www.csis.org/rss.xml",
        "think_tank", 0.8,
    ),
    SourceConfig(
        "The Diplomat (Asia-Pacifico)",
        "https://thediplomat.com/feed/",
        "think_tank", 0.7,
    ),
    # Carnegie y SIPRI bloquean/discontinuaron su RSS directo (verificado); via Google News.
    SourceConfig(
        "Carnegie Endowment for International Peace",
        _google_news_proxy("carnegieendowment.org", window="14d"),
        "think_tank", 0.8,
    ),
    SourceConfig(
        "SIPRI - Stockholm International Peace Research Institute",
        _google_news_proxy("sipri.org", window="14d"),
        "think_tank", 0.85,
    ),
    # Foreign Affairs (revista insignia del CFR) SI sirve RSS directo, a diferencia del propio
    # CFR de arriba -- verificado por separado. PIIE, Stimson Center y FPRI via Google News
    # (RSS directo devuelve 404 en los tres, verificado).
    SourceConfig(
        "Foreign Affairs",
        "https://www.foreignaffairs.com/rss.xml",
        "think_tank", 0.8,
    ),
    SourceConfig(
        "PIIE - Peterson Institute for International Economics",
        _google_news_proxy("piie.com", window="14d"),
        "think_tank", 0.85,
    ),
    SourceConfig(
        "Stimson Center",
        _google_news_proxy("stimson.org", window="14d"),
        "think_tank", 0.75,
    ),
    SourceConfig(
        "FPRI - Foreign Policy Research Institute",
        _google_news_proxy("fpri.org", window="14d"),
        "think_tank", 0.75,
    ),
    # Cobertura regional que la lista original no tenia: Europa continental (mas alla de UK),
    # Sur de Asia, Este Asiatico y Oriente Medio -- cada region analiza sus propios conflictos
    # con un angulo que Washington/Londres no siempre capta. Jamestown y Lowy tienen RSS
    # directo (verificado); el resto via Google News (RSS directo 403/404 en todos ellos).
    SourceConfig(
        "DGAP - German Council on Foreign Relations",
        _google_news_proxy("dgap.org", window="14d"),
        "think_tank", 0.75,
    ),
    SourceConfig(
        "ISPI - Istituto per gli Studi di Politica Internazionale (Italia)",
        _google_news_proxy("ispionline.it", window="14d"),
        "think_tank", 0.75,
    ),
    SourceConfig(
        "Real Instituto Elcano (Espana)",
        _google_news_proxy("realinstitutoelcano.org", window="14d"),
        "think_tank", 0.65,
    ),
    SourceConfig(
        "ORF - Observer Research Foundation (India)",
        _google_news_proxy("orfonline.org", window="14d"),
        "think_tank", 0.8,
    ),
    SourceConfig(
        "East Asia Forum",
        _google_news_proxy("eastasiaforum.org", window="7d"),
        "think_tank", 0.75,
    ),
    SourceConfig(
        "Middle East Institute",
        _google_news_proxy("mei.edu", window="14d"),
        "think_tank", 0.8,
    ),
    SourceConfig(
        "Al-Monitor (Oriente Medio)",
        _google_news_proxy("al-monitor.com", window="7d"),
        "think_tank", 0.75,
    ),
    SourceConfig(
        "Jamestown Foundation (Rusia/Eurasia)",
        "https://jamestown.org/feed/",
        "think_tank", 0.8,
    ),
    SourceConfig(
        "Lowy Institute - The Interpreter (Australia)",
        "https://www.lowyinstitute.org/the-interpreter/rss.xml",
        "think_tank", 0.8,
    ),
    SourceConfig(
        "ISEAS - Fulcrum (Sudeste Asiatico / ASEAN)",
        "https://fulcrum.sg/feed/",
        "think_tank", 0.8,
    ),
    # IFRI (Francia) y SAIIA (Sudafrica) se investigaron tambien -- 0 y 1 entradas utiles
    # respectivamente via proxy, demasiado debil. Se dejan fuera a proposito.
    #
    # LIMITACION CONOCIDA Y NO RESUELTA: America Latina no tiene voz propia en esta lista.
    # Se probaron CEBRI (Brasil, 2 entradas via proxy) y CARI (Argentina, 0 entradas) -- ambas
    # demasiado debiles para incluir. Si en el futuro se encuentra un instituto latinoamericano
    # con RSS real y activo (ej. algo equivalente a Elcano/DGAP pero para la region), deberia
    # anadirse aqui.

    # --- Defensa y seguridad: analisis especializado en conflicto armado, mas granular y
    #     tecnico que los think tanks generalistas de arriba; ayuda a que el motor de consenso
    #     detecte diversidad institucional real en eventos puramente militares/de defensa ---
    SourceConfig(
        "War on the Rocks",
        "https://warontherocks.com/feed/",
        "defensa_seguridad", 0.8,
    ),
    SourceConfig(
        "Defense One",
        "https://www.defenseone.com/rss/all/",
        "defensa_seguridad", 0.75,
    ),
    # Empezo a devolver 403 (proteccion anti-bot) durante la ronda de verificacion de esta
    # expansion -- funcionaba antes con RSS directo. Se cambia al mismo patron de proxy que el
    # resto de fuentes bloqueadas, en vez de dejarlo silenciosamente roto.
    SourceConfig(
        "Breaking Defense",
        _google_news_proxy("breakingdefense.com", window="7d"),
        "defensa_seguridad", 0.75,
    ),
    # ISW discontinuo su RSS directo (404 verificado); via Google News.
    SourceConfig(
        "Institute for the Study of War (ISW)",
        _google_news_proxy("understandingwar.org", window="7d"),
        "defensa_seguridad", 0.85,
    ),
    # IISS publica "The Military Balance", la referencia anual estandar de capacidad militar
    # por pais -- maxima autoridad en analisis de defensa comparado. NATO son comunicados
    # oficiales de la propia alianza (fuente primaria, no analisis de tercero). Ninguno de los
    # dos RSS directos funciona (403/404 verificado); via Google News.
    SourceConfig(
        "IISS - International Institute for Strategic Studies",
        _google_news_proxy("iiss.org", window="14d"),
        "defensa_seguridad", 0.85,
    ),
    SourceConfig(
        "NATO - News",
        _google_news_proxy("nato.int", window="7d"),
        "defensa_seguridad", 0.8,
    ),
    # RUSI (Reino Unido) es uno de los institutos de defensa mas antiguos y citados del mundo.
    # ISS Africa cubre conflictos africanos con un nivel de detalle que los think tanks
    # generalistas de arriba no alcanzan -- Africa estaba infrarrepresentada en la lista
    # original pese a concentrar buena parte de los conflictos activos registrados (ver
    # /api/conflicts). RSS directo de ambos falla (403/404 verificado); via Google News.
    SourceConfig(
        "RUSI - Royal United Services Institute (Reino Unido)",
        _google_news_proxy("rusi.org", window="14d"),
        "defensa_seguridad", 0.85,
    ),
    SourceConfig(
        "ISS Africa - Institute for Security Studies",
        _google_news_proxy("issafrica.org", window="14d"),
        "defensa_seguridad", 0.8,
    ),
    # Bellingcat: investigacion OSINT (fuente abierta) que VERIFICA sobre el terreno --
    # armamento, movimientos de tropas, crimenes de guerra -- con evidencia geolocalizada y
    # verificable, no ensayo de interpretacion. Complementa, no repite, a los think tanks de
    # arriba. RSS directo funciona sin proxy.
    SourceConfig(
        "Bellingcat (verificacion OSINT)",
        "https://www.bellingcat.com/feed/",
        "defensa_seguridad", 0.85,
    ),
]

# NOTA (ver README): Bloomberg/Reuters Terminal y otras fuentes premium no ofrecen RSS publico
# gratuito. Para incorporarlas, anade un `fetch_method="api"` y un conector dedicado en
# `fetchers.py` que use su API oficial con clave (NewsAPI, RapidAPI, etc.).
#
# Fuentes servidas via `_google_news_proxy`: su `link` apunta a un redirect de
# news.google.com, no a la URL directa del articulo (limitacion del propio servicio de Google,
# no del pipeline). Si en el futuro alguna institucion vuelve a ofrecer RSS directo estable,
# sustituye su entrada por la URL oficial para recuperar el enlace directo.
