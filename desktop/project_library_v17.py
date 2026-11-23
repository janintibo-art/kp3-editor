"""Local V17 project catalogue. Archives are immutable; never sends MIDI/Korg data."""
from pathlib import Path
import hashlib,json,os,shutil,tempfile,uuid,datetime
from common_project_v16 import inspect_project

MAX_BYTES=192*1024*1024
class ProjectLibrary:
    def __init__(self,root):
        self.root=Path(root)/'projects_v17';self.root.mkdir(parents=True,exist_ok=True)
        self.files=self.root/'archives';self.files.mkdir(exist_ok=True)
        self.index=self.root/'index.json'
    def _read(self):
        if not self.index.exists():return []
        data=json.loads(self.index.read_text(encoding='utf-8'))
        if not isinstance(data,list):raise ValueError('Catalogue de projets invalide')
        return data
    def _write(self,items):
        fd,tmp=tempfile.mkstemp(prefix='.index-',suffix='.tmp',dir=self.root)
        try:
            with os.fdopen(fd,'w',encoding='utf-8') as stream:
                json.dump(items,stream,indent=2,ensure_ascii=False)
                stream.flush();os.fsync(stream.fileno())
            os.replace(tmp,self.index)
        finally:
            if os.path.exists(tmp):os.unlink(tmp)
    def list(self):
        return sorted(self._read(),key=lambda a:a['created'],reverse=True)
    def archive(self,source,label=None):
        source=Path(source);size=source.stat().st_size
        if size>MAX_BYTES:raise ValueError('Archive trop volumineuse')
        data=inspect_project(source)
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        record={'id':uuid.uuid4().hex,'title':(label or data['title'])[:80],
          'created':datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'sha256':digest,'bytes':size,'samples':data['samples'],
          'pattern':data['pattern'],'synth':data['synth'],'origin':data['origin']}
        target=self.files/(record['id']+'.zip')
        try:
            with source.open('rb') as inp,target.open('xb') as out:shutil.copyfileobj(inp,out)
            self._write(self._read()+[record])
        except Exception:
            target.unlink(missing_ok=True)
            raise
        return record
    def locate(self,id):
        record=next((r for r in self._read() if r['id']==id),None)
        if record is None:raise ValueError('Projet introuvable')
        path=self.files/(record['id']+'.zip')
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:
            raise ValueError('Archive absente ou altérée')
        inspect_project(path)
        return path
    def duplicate(self,id):
        path=self.locate(id)
        record=next(r for r in self._read() if r['id']==id)
        return self.archive(path,record['title']+' (copie)')
    def export(self,id,target):
        src=self.locate(id);dest=Path(target)
        if dest.resolve()==src.resolve():raise ValueError('Destination identique')
        if dest.exists():raise FileExistsError('Fichier déjà existant : choisissez un autre nom')
        with src.open('rb') as inp,dest.open('xb') as out:shutil.copyfileobj(inp,out)
        return dest
    def remove_from_catalogue(self,id):
        # Never delete original archives: move to recovery before updating index.
        path=self.locate(id);recovery=self.root/'recovery';recovery.mkdir(exist_ok=True)
        shutil.move(str(path),str(recovery/path.name))
        self._write([r for r in self._read() if r['id']!=id])
