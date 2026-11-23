import { lazy, Suspense } from 'react'
import { Navigate, Route, Routes } from 'react-router-dom'
import { AppLayout } from '@/components/layout/AppLayout'
import { PainelAdminPage } from '@/pages/Admin/PainelAdminPage'
import { UsuariosPage } from '@/pages/Admin/UsuariosPage'
import { HomePage } from '@/pages/Home/HomePage'
import { EsqueciSenhaPage } from '@/pages/Login/EsqueciSenhaPage'
import { LoginPage } from '@/pages/Login/LoginPage'
import { RedefinirSenhaPage } from '@/pages/Login/RedefinirSenhaPage'
import { MinhasOcorrenciasPage } from '@/pages/MinhasOcorrencias/MinhasOcorrenciasPage'
import { NovaDenunciaPage } from '@/pages/NovaDenuncia/NovaDenunciaPage'
import { PerfilPage } from '@/pages/Perfil/PerfilPage'
import { PrivacidadePage } from '@/pages/Privacidade/PrivacidadePage'
import { NovoChamadoPage } from '@/pages/NovoChamado/NovoChamadoPage'
import { SegurancaHomePage } from '@/pages/Home/SegurancaHomePage'
import { TecnicoHomePage } from '@/pages/Home/TecnicoHomePage'
import { SosPage } from '@/pages/Sos/SosPage'
import { useAuth } from '@/hooks/useAuth'
import { ProtectedRoute } from './ProtectedRoute'

const AreasCampusPage = lazy(async () => {
  const modulo = await import('@/pages/Admin/AreasCampusPage')
  return { default: modulo.AreasCampusPage }
})

function Inicio() {
  const { usuario } = useAuth()
  if (usuario?.perfil === 'seguranca') return <SegurancaHomePage />
  if (usuario?.perfil === 'tecnico') return <TecnicoHomePage />
  return <HomePage />
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/esqueci-senha" element={<EsqueciSenhaPage />} />
      <Route path="/redefinir-senha" element={<RedefinirSenhaPage />} />
      <Route path="/privacidade" element={<PrivacidadePage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<Inicio />} />
          <Route path="perfil" element={<PerfilPage />} />

          <Route element={<ProtectedRoute perfis={['usuario']} />}>
            <Route path="novo-chamado" element={<NovoChamadoPage />} />
            <Route path="nova-denuncia" element={<NovaDenunciaPage />} />
            <Route path="sos/:id" element={<SosPage />} />
            <Route path="minhas-ocorrencias" element={<MinhasOcorrenciasPage />} />
          </Route>

          <Route element={<ProtectedRoute perfis={['admin']} />}>
            <Route path="admin" element={<PainelAdminPage />} />
            <Route path="admin/usuarios" element={<UsuariosPage />} />
            <Route path="admin/areas-campus" element={<Suspense fallback={<p className="text-sm text-muted">Carregando mapa…</p>}><AreasCampusPage /></Suspense>} />
          </Route>
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
