from fastapi.param_functions import Query
import math
from datetime import date, datetime
from typing import List

from app.db.db import db
from app.enums.medicion import TipoMedicion
from app.models.establecimiento import EstablecimientoDB
from app.models.gerente import Gerente
from app.models.medicion import Media, Medicion, MedicionEstablecimiento, MedicionRet
from app.utils.security import get_current_gerente
from fastapi import Depends, HTTPException
from fastapi.routing import APIRouter
from odmantic import ObjectId
from starlette import status

router = APIRouter(prefix="/medicion", tags=["Mediciones"])


@router.get("/medicion/{tipo}/{establecimiento_id}", response_model=MedicionRet)
async def obtener_ultima_medicion(
    establecimiento_id: ObjectId,
    tipo: TipoMedicion,
    gerente: Gerente = Depends(get_current_gerente),
):
    establecimiento = await obten_establecimiento(establecimiento_id,gerente)
   
    if establecimiento.mediciones is None:
        return MedicionRet()
    else:
        mediciones = filtra_dia(establecimiento.mediciones, tipo,fecha=datetime.now())
        ultima = mediciones[-1].contenido if len(mediciones) > 0 else 0
        return MedicionRet(contenido=ultima)


@router.get("/informe/diario", response_model=List[MedicionEstablecimiento])
async def obtener_mediciones(
    *,
    day: int = Query(date.today().day, le=31, ge=1),
    month: int = Query(date.today().month, le=12, ge=1),
    year: int = Query(date.today().year),
    gerente: Gerente = Depends(get_current_gerente),
):
    # Conversión fecha
    try:
        fecha = datetime(year, month, day)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{e}")

    establecimientos = await db.motor.find(
        EstablecimientoDB, EstablecimientoDB.gerente == gerente.id
    )

    res = []
    for establecimiento in establecimientos:
        if len(establecimiento.mediciones) > 0:

            est = obten_mediciones(fecha, establecimiento)
            res.append(est)
        else:
            res.append(
                MedicionEstablecimiento(
                    descriptor=establecimiento.descriptor,
                    id_establecimiento=str(establecimiento.id),
                )
            )
    return res


@router.get(
    "/informe/diario/{establecimiento_id}", response_model=MedicionEstablecimiento
)
async def obtener_mediciones_establecimiento(
    *,
    day: int = Query(date.today().day, le=31, ge=1),
    month: int = Query(date.today().month, le=12, ge=1),
    year: int = Query(date.today().year),
    establecimiento_id: ObjectId,
    gerente: Gerente = Depends(get_current_gerente),
):
    # Conversión fecha
    try:
        fecha = datetime(year, month, day)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{e}")

    establecimiento = await obten_establecimiento(establecimiento_id,gerente)

    

    if len(establecimiento.mediciones) > 0:

        return obten_mediciones(fecha, establecimiento)

    else:

        return MedicionEstablecimiento(
            descriptor=establecimiento.descriptor,
            id_establecimiento=str(establecimiento.id),
        )


def obten_mediciones(fecha, establecimiento) -> MedicionEstablecimiento:
    mediciones_aforo = filtra_mediciones(
        establecimiento.mediciones, TipoMedicion.aforo, fecha
    )
    ultima_media_aforo = mediciones_aforo[-1].media if len(mediciones_aforo) > 0 else 0
    mediciones_aire = filtra_mediciones(
        establecimiento.mediciones, TipoMedicion.aire, fecha
    )
    ultima_media_aire = mediciones_aire[-1].media if len(mediciones_aire) > 0 else 0
    mediciones_mascarillas = filtra_mediciones(
        establecimiento.mediciones, TipoMedicion.mascarillas, fecha
    )
    ultima_media_mascarillas = mediciones_mascarillas[-1].media if len(mediciones_mascarillas) > 0 else 0
    est = MedicionEstablecimiento(
        descriptor=establecimiento.descriptor,
        id_establecimiento=str(establecimiento.id),
        aforo_value=ultima_media_aforo,
        medias_aforo=mediciones_aforo,
        aire_value=ultima_media_aire,
        medias_aire=mediciones_aire,
        mascarillas_value=ultima_media_mascarillas,
        medias_mascarillas=mediciones_mascarillas,
    )
    return est


def filtra_mediciones(mediciones: List[Medicion], tipo: TipoMedicion, fecha: datetime):
    return media_mediciones(filtra_dia(mediciones, tipo, fecha=fecha))


def media_mediciones(mediciones: list[Medicion]):
    medias = []
    for h in range(24):
        l = list(filter(lambda x: x.fecha.hour == h, mediciones))
        if len(l) > 0:
            valores = list(map(lambda x: float(x.contenido), l))
            avg = sum(valores) / len(valores)
            medias.append(Media(hora=h, media=math.ceil(avg)))
    return medias


def filtra_dia(
    mediciones: list[Medicion], tipo: TipoMedicion, fecha: datetime
) -> list[Medicion]:
    return list(
        filter(
            lambda medicion: medicion.tipo_medicion == tipo
            and medicion.fecha.date() == fecha.date(),
            mediciones,
        )
    )


def filtra_fecha(
    mediciones: Medicion,
    tipo: TipoMedicion,
    fecha_ini: datetime = None,
    fecha_fin: datetime = None,
) -> list[Medicion]:

    return list(
        filter(
            lambda medicion: medicion.tipo_medicion == tipo
            and (fecha_fin is None or medicion.fecha <= fecha_fin)
            and (fecha_ini is None or medicion.fecha >= fecha_ini),
            mediciones,
        )
    )


async def obten_establecimiento(establecimiento_id: ObjectId,gerente:Gerente):
    establecimiento = await db.motor.find_one(
        EstablecimientoDB, EstablecimientoDB.id == establecimiento_id
    )
    if establecimiento is None:
        raise HTTPException(
            detail="Ese establecimiento no existe",
            status_code=status.HTTP_404_NOT_FOUND,
        )
    if establecimiento.gerente.id != gerente.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Establecimiento no en propiedad",
        )
    return establecimiento
