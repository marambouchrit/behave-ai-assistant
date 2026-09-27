import AdminSidebar from "../components/admin/AdminSidebar";
import ChatLayout   from "../components/ChatLayout";

// L'admin dispose de la même gestion de conversations qu'un utilisateur ;
// son compte et sa déconnexion restent dans la barre de navigation admin.
function AdminChat() {
  return (
    <div className="h-screen flex">
      <AdminSidebar activePage="chat" />
      <ChatLayout showAccountFooter={false} />
    </div>
  );
}

export default AdminChat;
