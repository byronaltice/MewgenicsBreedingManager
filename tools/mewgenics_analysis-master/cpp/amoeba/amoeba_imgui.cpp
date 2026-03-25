#include "amoeba.hpp"
#include "types/glaiel.hpp"
#include "utilities/debug_console.hpp"
#include "utilities/function_hook.hpp"
#include "utilities/strings.hpp"
#include "utilities/memory.hpp"

#include "SDL3/SDL.h"
#include "imgui.h"
#include "imgui_impl_sdl3.h"
#include "imgui_impl_opengl3.h"

// Cat therapy? Sign me up!
//
// Injects imgui into Mewgenics to facilitate in-process exploration.
//
// polymeric 2026

struct ImguiPrivateState {
    bool initialized = false;
    bool swapwindow_hook_nested_call_guard = false;
    bool request_dll_eject = false;

    bool hide_all = false;
    bool show_feline_therapist = false;
    bool show_data_explorer = false;
    bool show_debug_console = false;
    bool show_imgui_demo = false;
};

static ImguiPrivateState P;

template<class... Args>
void ImguiTextStdFmt(std::format_string<Args...> fmt, Args&&... args) {
    std::string s = std::format(fmt, std::forward<Args>(args)...);
    ImGui::TextUnformatted(s.data(), s.data() + s.size());
}

void show_about_modal(bool signal) {
    if(signal) {
        ImGui::OpenPopup("About Amoeba");
    }
    // Always center this window when appearing
    ImVec2 center = ImGui::GetMainViewport()->GetCenter();
    ImGui::SetNextWindowPos(center, ImGuiCond_Appearing, ImVec2(0.5f, 0.5f));
    bool x_button = true;
    if(ImGui::BeginPopupModal("About Amoeba", &x_button, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImguiTextStdFmt("Amoeba, a Mewgenics exploration tool.");
        ImguiTextStdFmt("© polymeric. All rights reserved.");
        ImguiTextStdFmt("Provided under the terms of the MIT license.");
        ImGui::TextLinkOpenURL("https://github.com/p0lymeric/mewgenics_analysis");
        ImGui::Separator();

        ImGui::SetItemDefaultFocus();
        if(ImGui::Button("Close", ImVec2(120, 0)) || !x_button) {
            ImGui::CloseCurrentPopup();
        }
        ImGui::EndPopup();
    }
}

void show_eject_confirmation_modal(bool signal) {
    if(signal) {
        ImGui::OpenPopup("Eject?");
    }
    // Always center this window when appearing
    ImVec2 center = ImGui::GetMainViewport()->GetCenter();
    ImGui::SetNextWindowPos(center, ImGuiCond_Appearing, ImVec2(0.5f, 0.5f));
    bool x_button = true;
    if(ImGui::BeginPopupModal("Eject?", &x_button, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImguiTextStdFmt("Really eject Amoeba?");
        ImGui::Separator();

        if(ImGui::Button("Yes", ImVec2(120, 0))) {
            P.request_dll_eject = true;
            ImGui::CloseCurrentPopup();
        }
        ImGui::SetItemDefaultFocus();
        ImGui::SameLine();
        if(ImGui::Button("No", ImVec2(120, 0)) || !x_button) {
            ImGui::CloseCurrentPopup();
        }
        ImGui::EndPopup();
    }
}

void show_exit_confirmation_modal(bool signal) {
    if(signal) {
        ImGui::OpenPopup("Kill process?");
    }
    // Always center this window when appearing
    ImVec2 center = ImGui::GetMainViewport()->GetCenter();
    ImGui::SetNextWindowPos(center, ImGuiCond_Appearing, ImVec2(0.5f, 0.5f));
    bool x_button = true;
    if(ImGui::BeginPopupModal("Kill process?", &x_button, ImGuiWindowFlags_AlwaysAutoResize)) {
        ImguiTextStdFmt("Really kill the game's process?");
        ImguiTextStdFmt("(Steven won't know.)");
        ImGui::Separator();

        if(ImGui::Button("Yes", ImVec2(120, 0))) {
            do_process_termination();
            // unreachable
            ImGui::CloseCurrentPopup();
        }
        ImGui::SetItemDefaultFocus();
        ImGui::SameLine();
        if(ImGui::Button("No", ImVec2(120, 0)) || !x_button) {
            ImGui::CloseCurrentPopup();
        }
        ImGui::EndPopup();
    }
}

void show_main_menu_bar() {
    bool signal_eject_confirmation_modal = false;
    bool signal_exit_confirmation_modal = false;
    bool signal_about_modal = false;

    if(ImGui::BeginMainMenuBar()) {
        if(ImGui::BeginMenu("File")) {
            if(ImGui::MenuItem("Eject Amoeba")) { signal_eject_confirmation_modal = true; }
            if(ImGui::MenuItem("Kill process")) { signal_exit_confirmation_modal = true; }
            ImGui::EndMenu();
        }
        if(ImGui::BeginMenu("Tools")) {
            if(ImGui::MenuItem("Show Feline Therapist", NULL, &P.show_feline_therapist)) {}
            if(ImGui::MenuItem("Show data explorer", NULL, &P.show_data_explorer)) {}
            if(ImGui::MenuItem("Show debug console", NULL, &P.show_debug_console)) {}
            ImGui::EndMenu();
        }
        if(ImGui::BeginMenu("Help")) {
            if(ImGui::MenuItem("Show Dear ImGui demo", NULL, &P.show_imgui_demo)) {}
            ImGui::Separator();
            if(ImGui::MenuItem("About Amoeba")) { signal_about_modal = true; }
            ImGui::EndMenu();
        }
        ImGui::EndMainMenuBar();
    }

    show_eject_confirmation_modal(signal_eject_confirmation_modal);
    show_exit_confirmation_modal(signal_exit_confirmation_modal);
    show_about_modal(signal_about_modal);
}

void show_debug_console_window() {
    if(!P.show_debug_console) {
        return;
    }
    ImVec2 viewport_size = ImGui::GetMainViewport()->Size;
    ImGui::SetNextWindowSize(ImVec2(viewport_size.x * 0.4f, viewport_size.y * 0.4f), ImGuiCond_FirstUseEver);
    if(ImGui::Begin("Debug console", &P.show_debug_console)) {
        if(ImGui::BeginChild("Scroller", ImVec2(0, 0), ImGuiChildFlags_None, ImGuiWindowFlags_HorizontalScrollbar)) {
            ImGuiListClipper clipper;
            int log_size = static_cast<int>(D::get().internal_buffer.size());
            clipper.Begin(log_size);
            while(clipper.Step()) {
                for(int i = clipper.DisplayStart; i < clipper.DisplayEnd; i++) {
                    auto message = D::get().internal_buffer[log_size - i - 1];
                    // FIXME scrolling is broken. ImGuiListClipper is not a correct solution for handling multiline strings
                    ImGui::TextUnformatted(message.message.data(), message.message.data() + message.message.size());
                }
            }
            clipper.End();
        }
        ImGui::EndChild();
    }
    ImGui::End();
}

void show_data_explorer_window() {
    if(!P.show_data_explorer) {
        return;
    }
    ImVec2 viewport_size = ImGui::GetMainViewport()->Size;
    ImGui::SetNextWindowSize(ImVec2(viewport_size.x * 0.4f, viewport_size.y * 0.4f), ImGuiCond_FirstUseEver);
    if(ImGui::Begin("Data explorer", &P.show_data_explorer)) {
        // good architecture, just need to null check one global and you're ready to go!
        MewDirector *p_md = *reinterpret_cast<MewDirector **>(ADDRESS_glaiel__MewDirector__p_singleton + G.host_exec_base_va);

        if(ImGui::TreeNode("Pointers")) {
            ImguiTextStdFmt("Hook base VA: {:p}", reinterpret_cast<void *>(G.dll_base_va));
            ImguiTextStdFmt("Executable base VA: {:p}", reinterpret_cast<void *>(G.host_exec_base_va));
            ImguiTextStdFmt("p_MewDirector: {:p}", static_cast<void *>(p_md));
            if(p_md != nullptr) {
                CatDatabase *p_cdb = p_md->cats;
                ImguiTextStdFmt("p_CatDatabase: {:p}", static_cast<void *>(p_cdb));
            }
            ImGui::TreePop();
        }

        if(ImGui::TreeNode("Thread-local storage")) {
            auto *p_tls = get_tls0_base<LAYOUT_TLS_Slot0>();
            ImguiTextStdFmt("TLS base: {:p}", reinterpret_cast<void *>(p_tls));
            for(int i = 0; i < 4; i++) {
                ImguiTextStdFmt("RNG context {}: 0x{:x}", i, p_tls->xoshiro256p_rng_context[i]);
            }
            ImGui::TreePop();
        }

        if(ImGui::TreeNode("Loaded cats")) {
            if(p_md != nullptr) {
                // if(ImGui::Button("Load cat 1")) {
                //     using FP = CatData *(*)(CatDatabase *thiss, int32_t sql_key);
                //     auto fp = *reinterpret_cast<FP>(ADDRESS_glaiel__CatDatabase__UnkCachingLoad + G.host_exec_base_va);
                //     fp(p_md->cats, 1);
                // }
                // the game appears to lazy-query cats as needed to view loved/hated cat names and family tree portraits
                auto &cats = p_md->cats->cats;
                ImguiTextStdFmt("Size: {}", cats._List._Mysize);
                if(ImGui::BeginTable("table1", 4)) {
                    ImGui::TableSetupColumn("Cat", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                    ImGui::TableSetupColumn("Name", ImGuiTableColumnFlags_WidthStretch, 3.0f);
                    ImGui::TableSetupColumn("Symbol", ImGuiTableColumnFlags_WidthStretch, 2.0f);
                    ImGui::TableSetupColumn("p_CatData", ImGuiTableColumnFlags_WidthStretch, 2.0f);
                    ImGui::TableHeadersRow();
                    auto head = cats._List._Myhead;
                    auto current = head->_Next;
                    while(current != head) {
                        auto &cat = *current->_Myval.cat;
                        ImGui::TableNextRow();
                        ImGui::TableNextColumn();
                        ImguiTextStdFmt("{}", current->_Myval.sql_key);
                        ImGui::TableNextColumn();
                        ImguiTextStdFmt("{}", convert_utf16_wstring_to_utf8_string(cat.name));
                        ImGui::TableNextColumn();
                        ImguiTextStdFmt("{}", cat.nameplate_symbol);
                        ImGui::TableNextColumn();
                        ImguiTextStdFmt("{:p}", reinterpret_cast<void *>(&cat));
                        current = current->_Next;
                    }
                    ImGui::EndTable();
                }
                if(ImGui::TreeNode("Show hash map details")) {
                    ImguiTextStdFmt("_Max_bucket_size: {:f}", cats._Max_bucket_size);
                    ImguiTextStdFmt("_Mask: 0x{:x}", cats._Mask);
                    ImguiTextStdFmt("_Maxidx: 0x{:x}", cats._Maxidx);
                    ImguiTextStdFmt("_Unchecked_end: {:p}", reinterpret_cast<void *>(cats._List._Myhead));
                    if(ImGui::BeginTable("table1", 3)) {
                        ImGui::TableSetupColumn("Bucket", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                        ImGui::TableSetupColumn("Start (incl)", ImGuiTableColumnFlags_WidthStretch, 2.0f);
                        ImGui::TableSetupColumn("End (incl)", ImGuiTableColumnFlags_WidthStretch, 2.0f);
                        ImGui::TableHeadersRow();
                        size_t i = 0;
                        for(auto p_bucket = cats._Vec._Myfirst; p_bucket < cats._Vec._Mylast; p_bucket++) {
                            ImGui::TableNextRow();
                            ImGui::TableNextColumn();
                            ImguiTextStdFmt("{:02x}", i);
                            ImGui::TableNextColumn();
                            ImguiTextStdFmt("{}", reinterpret_cast<void *>(p_bucket->first));
                            ImGui::TableNextColumn();
                            ImguiTextStdFmt("{}", reinterpret_cast<void *>(p_bucket->last));
                            i++;
                        }
                        ImGui::EndTable();
                    }
                    ImGui::TreePop();
                }
            }
            ImGui::TreePop();
        }

        if(ImGui::TreeNode("Cats to delete")) {
            if(p_md != nullptr) {
                // the game appears to delete kittens and strays if they are discarded on their first day at the house
                // (unsure what happens with donations, or discarding a cat met on an adventure)
                auto &cats = p_md->cats->cats_to_delete;
                ImguiTextStdFmt("Size: {}", cats._List._Mysize);
                if(ImGui::BeginTable("table1", 1)) {
                    ImGui::TableSetupColumn("Cat", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                    ImGui::TableHeadersRow();
                    auto head = cats._List._Myhead;
                    auto current = head->_Next;
                    while(current != head) {
                        ImGui::TableNextRow();
                        ImGui::TableNextColumn();
                        ImguiTextStdFmt("{}", current->_Myval);
                        current = current->_Next;
                    }
                    ImGui::EndTable();
                }
                if(ImGui::TreeNode("Show hash map details")) {
                    ImguiTextStdFmt("_Max_bucket_size: {:f}", cats._Max_bucket_size);
                    ImguiTextStdFmt("_Mask: 0x{:x}", cats._Mask);
                    ImguiTextStdFmt("_Maxidx: 0x{:x}", cats._Maxidx);
                    ImguiTextStdFmt("_Unchecked_end: {:p}", reinterpret_cast<void *>(cats._List._Myhead));
                    if(ImGui::BeginTable("table1", 3)) {
                        ImGui::TableSetupColumn("Bucket", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                        ImGui::TableSetupColumn("Start (incl)", ImGuiTableColumnFlags_WidthStretch, 2.0f);
                        ImGui::TableSetupColumn("End (incl)", ImGuiTableColumnFlags_WidthStretch, 2.0f);
                        ImGui::TableHeadersRow();
                        size_t i = 0;
                        for(auto p_bucket = cats._Vec._Myfirst; p_bucket < cats._Vec._Mylast; p_bucket++) {
                            ImGui::TableNextRow();
                            ImGui::TableNextColumn();
                            ImguiTextStdFmt("{:02x}", i);
                            ImGui::TableNextColumn();
                            ImguiTextStdFmt("{}", reinterpret_cast<void *>(p_bucket->first));
                            ImGui::TableNextColumn();
                            ImguiTextStdFmt("{}", reinterpret_cast<void *>(p_bucket->last));
                            i++;
                        }
                        ImGui::EndTable();
                    }
                    ImGui::TreePop();
                }
            }
            ImGui::TreePop();
        }

        if(ImGui::TreeNode("Pedigree map")) {
            if(p_md != nullptr) {
                auto &map = p_md->cats->pedigree.child_to_parents_and_coi_map;
                ImguiTextStdFmt("Size, cap, growth_left: {}, {}, {}", map.size, map.cap, map.growth_left);
                ImguiTextStdFmt("Hashing test passed: {}", map.verify_get());
                if(ImGui::BeginTable("table1", 6)) {
                    ImGui::TableSetupColumn("Slot", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                    ImGui::TableSetupColumn("H2", ImGuiTableColumnFlags_WidthStretch, 0.5f);
                    ImGui::TableSetupColumn("Child", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                    ImGui::TableSetupColumn("Parent A", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                    ImGui::TableSetupColumn("Parent B", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                    ImGui::TableSetupColumn("COI", ImGuiTableColumnFlags_WidthStretch, 2.0f);
                    ImGui::TableHeadersRow();

                    for(size_t i = 0; i < map.cap; i++) {
                        if(map.ctrl[i] <= 0x7F) {
                            auto entry = map.slots[i];
                            ImGui::TableNextRow();
                            ImGui::TableNextColumn();
                            ImguiTextStdFmt("{}", i);
                            ImGui::TableNextColumn();
                            ImguiTextStdFmt("{:02x}", map.ctrl[i]);
                            ImGui::TableNextColumn();
                            ImguiTextStdFmt("{}", entry.key);
                            ImGui::TableNextColumn();
                            ImguiTextStdFmt("{}", entry.val.parent_a);
                            ImGui::TableNextColumn();
                            ImguiTextStdFmt("{}", entry.val.parent_b);
                            ImGui::TableNextColumn();
                            ImguiTextStdFmt("{}", entry.val.coi);
                        }
                    }
                    ImGui::EndTable();
                }
            }
            ImGui::TreePop();
        }

        if(ImGui::TreeNode("Parent COI map")) {
            if(p_md != nullptr) {
                auto &map = p_md->cats->pedigree.parents_to_coi_memo_map;
                ImguiTextStdFmt("Size, cap, growth_left: {}, {}, {}", map.size, map.cap, map.growth_left);
                ImguiTextStdFmt("Hashing test passed: {}", map.verify_get());
                if(ImGui::BeginTable("table1", 5)) {
                    ImGui::TableSetupColumn("Slot", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                    ImGui::TableSetupColumn("H2", ImGuiTableColumnFlags_WidthStretch, 0.5f);
                    ImGui::TableSetupColumn("Parent A", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                    ImGui::TableSetupColumn("Parent B", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                    ImGui::TableSetupColumn("COI", ImGuiTableColumnFlags_WidthStretch, 2.0f);
                    ImGui::TableHeadersRow();

                    for(size_t i = 0; i < map.cap; i++) {
                        if(map.ctrl[i] <= 0x7F) {
                            auto entry = map.slots[i];
                            ImGui::TableNextRow();
                            ImGui::TableNextColumn();
                            ImguiTextStdFmt("{}", i);
                            ImGui::TableNextColumn();
                            ImguiTextStdFmt("{:02x}", map.ctrl[i]);
                            ImGui::TableNextColumn();
                            ImguiTextStdFmt("{}", entry.key.parent_a);
                            ImGui::TableNextColumn();
                            ImguiTextStdFmt("{}", entry.key.parent_b);
                            ImGui::TableNextColumn();
                            ImguiTextStdFmt("{}", entry.val);
                        }
                    }
                    ImGui::EndTable();
                }
            }
            ImGui::TreePop();
        }

        if(ImGui::TreeNode("Accessible cat set")) {
            if(p_md != nullptr) {
                auto &map = p_md->cats->pedigree.accessible_cats;
                ImguiTextStdFmt("Size, cap, growth_left: {}, {}, {}", map.size, map.cap, map.growth_left);
                ImguiTextStdFmt("Hashing test passed: {}", map.verify_get());
                if(ImGui::BeginTable("table1", 3)) {
                    ImGui::TableSetupColumn("Slot", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                    ImGui::TableSetupColumn("H2", ImGuiTableColumnFlags_WidthStretch, 0.5f);
                    ImGui::TableSetupColumn("Cat", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                    ImGui::TableHeadersRow();

                    for(size_t i = 0; i < map.cap; i++) {
                        if(map.ctrl[i] <= 0x7F) {
                            auto entry = map.slots[i];
                            ImGui::TableNextRow();
                            ImGui::TableNextColumn();
                            ImguiTextStdFmt("{}", i);
                            ImGui::TableNextColumn();
                            ImguiTextStdFmt("{:02x}", map.ctrl[i]);
                            ImGui::TableNextColumn();
                            ImguiTextStdFmt("{}", entry.key);
                        }
                    }
                    ImGui::EndTable();
                }
            }
            ImGui::TreePop();
        }

        if(ImGui::TreeNode("Generated name history")) {
            if(p_md != nullptr) {
                auto &names = p_md->cats->name_gen_history_w;
                ImguiTextStdFmt("Size, capacity: {}, {}", names.size(), names.capacity());
                if(ImGui::BeginTable("table1", 1)) {
                    ImGui::TableSetupColumn("Name", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                    ImGui::TableHeadersRow();
                    for(auto p_name = names._Myfirst; p_name < names._Mylast; p_name++) {
                        ImGui::TableNextRow();
                        ImGui::TableNextColumn();
                        ImguiTextStdFmt("{}", convert_utf16_wstring_to_utf8_string(*p_name));
                    }
                    ImGui::EndTable();
                }
            }
            ImGui::TreePop();
        }
    }
    ImGui::End();
}

void show_feline_therapist_window() {
    if(!P.show_feline_therapist) {
        return;
    }
    ImVec2 viewport_size = ImGui::GetMainViewport()->Size;
    ImGui::SetNextWindowSize(ImVec2(viewport_size.x * 0.4f, viewport_size.y * 0.4f), ImGuiCond_FirstUseEver);
    if(ImGui::Begin("Feline Therapist", &P.show_feline_therapist)) {
        if(ImGui::BeginChild("Scroller", ImVec2(0, 0), ImGuiChildFlags_None, ImGuiWindowFlags_HorizontalScrollbar)) {
            MewDirector *p_md = *reinterpret_cast<MewDirector **>(ADDRESS_glaiel__MewDirector__p_singleton + G.host_exec_base_va);
            if(p_md != nullptr) {
                CatDatabase *p_cdb = p_md->cats;
                auto head = p_cdb->cats._List._Myhead;
                auto current = head->_Next;
                while(current != head) {
                    auto &cat = *current->_Myval.cat;
                    if(ImGui::TreeNode(std::format("{} ({})", convert_utf16_wstring_to_utf8_string(cat.name), current->_Myval.sql_key).c_str())) {
                        ImguiTextStdFmt("p_CatData: {:p}", reinterpret_cast<void *>(&cat));
                        ImguiTextStdFmt("Nameplate symbol: {}", cat.nameplate_symbol);
                        ImguiTextStdFmt("Entropy: 0x{:x}", cat.entropy);
                        ImguiTextStdFmt("Sex: {} {}", cat.sex, cat.sex_dup);
                        ImguiTextStdFmt("Flags: 0x{:x}", cat.flags);
                        std::string flags_list = "";
                        for(int i = 63; i >= 0; i--) {
                            if((cat.flags >> i) & 1) {
                                flags_list += std::format("{} ", i);
                            }
                        }
                        ImguiTextStdFmt("Flags: {}", flags_list);
                        ImguiTextStdFmt("unknown 2/3: {} {}", cat.unknown_2, cat.unknown_3);
                        ImguiTextStdFmt("Libido: {}", cat.libido);
                        ImguiTextStdFmt("Sexuality: {}", cat.sexuality);
                        ImguiTextStdFmt("Loves: {} ({})", cat.lover_sql_key, cat.unknown_7);
                        ImguiTextStdFmt("Aggression: {}", cat.aggression);
                        ImguiTextStdFmt("Hates: {} ({})", cat.hater_sql_key, cat.unknown_9);
                        ImguiTextStdFmt("Fertility: {}", cat.fertility);
                        ImguiTextStdFmt("Texture/palettes: {} {} {}", cat.body_parts.texture_sprite_idx, cat.body_parts.heritable_palette_idx, cat.body_parts.collar_palette_idx);
                        ImguiTextStdFmt("BodyParts.unknown_0/1: {} {}", cat.body_parts.unknown_0, cat.body_parts.unknown_1);
                        ImguiTextStdFmt("BodyPartDescriptors");
                        if(ImGui::BeginTable("bodyparts_table", 6)) {
                            ImGui::TableSetupColumn("Part", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                            ImGui::TableSetupColumn("part_sprite", ImGuiTableColumnFlags_WidthStretch, 0.5f);
                            ImGui::TableSetupColumn("texture_sprite", ImGuiTableColumnFlags_WidthStretch, 0.5f);
                            ImGui::TableSetupColumn("unknown_0", ImGuiTableColumnFlags_WidthStretch, 0.5f);
                            ImGui::TableSetupColumn("unknown_1", ImGuiTableColumnFlags_WidthStretch, 0.5f);
                            ImGui::TableSetupColumn("unknown_2", ImGuiTableColumnFlags_WidthStretch, 0.5f);
                            ImGui::TableHeadersRow();
                            BodyPartDescriptor *p_base = &cat.body_parts.body;
                            for(uint32_t i = 0; i < 14; i++) {
                                ImGui::TableNextRow();
                                ImGui::TableNextColumn();
                                const char *label = i == 0 ? "body" :
                                                    i == 1 ? "head" :
                                                    i == 2 ? "tail" :
                                                    i == 3 ? "leg1" :
                                                    i == 4 ? "leg2" :
                                                    i == 5 ? "arm1" :
                                                    i == 6 ? "arm2" :
                                                    i == 7 ? "lefteye" :
                                                    i == 8 ? "righteye" :
                                                    i == 9 ? "lefteyebrow" :
                                                    i == 10 ? "righteyebrow" :
                                                    i == 11 ? "leftear" :
                                                    i == 12 ? "rightear" :
                                                    "mouth";
                                ImguiTextStdFmt("{}", label);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_base[i].part_sprite_idx);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_base[i].texture_sprite_idx);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_base[i].unknown_0);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_base[i].unknown_1);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_base[i].unknown_2);
                            }
                            ImGui::EndTable();
                        }
                        ImguiTextStdFmt("Voice: {} ({})", cat.body_parts.voice, cat.body_parts.pitch);
                        ImguiTextStdFmt("Stats");
                        if(ImGui::BeginTable("stats_table", 8)) {
                            ImGui::TableSetupColumn("Kind", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                            ImGui::TableSetupColumn("str", ImGuiTableColumnFlags_WidthStretch, 0.3f);
                            ImGui::TableSetupColumn("dex", ImGuiTableColumnFlags_WidthStretch, 0.3f);
                            ImGui::TableSetupColumn("con", ImGuiTableColumnFlags_WidthStretch, 0.3f);
                            ImGui::TableSetupColumn("int", ImGuiTableColumnFlags_WidthStretch, 0.3f);
                            ImGui::TableSetupColumn("spd", ImGuiTableColumnFlags_WidthStretch, 0.3f);
                            ImGui::TableSetupColumn("cha", ImGuiTableColumnFlags_WidthStretch, 0.3f);
                            ImGui::TableSetupColumn("lck", ImGuiTableColumnFlags_WidthStretch, 0.3f);
                            ImGui::TableHeadersRow();
                            CatStats *p_base = &cat.stats_heritable;
                            for(uint32_t i = 0; i < 3; i++) {
                                ImGui::TableNextRow();
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", i == 0 ? "Heritable" : i == 1 ? "Levelling/Events" : "Injuries");
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_base[i].str);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_base[i].dex);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_base[i].con);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_base[i].int_);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_base[i].spd);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_base[i].cha);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_base[i].lck);
                            }
                            ImGui::EndTable();
                        }
                        ImguiTextStdFmt("Last debuff: {}", cat.last_injury_debuffed_stat);
                        ImguiTextStdFmt("HP: {}", cat.campaign_stats.hp);
                        ImguiTextStdFmt("Dead: {}", cat.campaign_stats.dead);
                        ImguiTextStdFmt("CampaignStats.unknown_0: {}", cat.campaign_stats.unknown_0);
                        ImguiTextStdFmt("CampaignStats.unknown_1: {}", cat.campaign_stats.unknown_1);
                        ImguiTextStdFmt("Event Stat Modifiers");
                        if(ImGui::BeginTable("event_stat_modifiers_table", 3)) {
                            ImGui::TableSetupColumn("pointer", ImGuiTableColumnFlags_WidthStretch, 0.5f);
                            ImGui::TableSetupColumn("Expression", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                            ImGui::TableSetupColumn("Battles remaining", ImGuiTableColumnFlags_WidthStretch, 0.5f);
                            ImGui::TableHeadersRow();
                            for(auto p_mod = cat.campaign_stats.event_stat_modifiers._Myfirst; p_mod < cat.campaign_stats.event_stat_modifiers._Mylast; p_mod++) {
                                ImGui::TableNextRow();
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{:p}", reinterpret_cast<void *>(p_mod));
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_mod->expression.SaveToStr(true));
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_mod->battles_remaining);
                            }
                            ImGui::EndTable();
                        }
                        for(int i = 0; i < 2; i++) {
                            auto p_base = cat.actives_basic;
                            ImguiTextStdFmt("Basic {}: {}", i, p_base[i]);
                        }
                        for(int i = 0; i < 4; i++) {
                            auto p_base = cat.actives_accessible;
                            ImguiTextStdFmt("Active (accessible) {}: {}", i, p_base[i]);
                        }
                        for(int i = 0; i < 4; i++) {
                            auto p_base = cat.actives_inherited;
                            ImguiTextStdFmt("Active (inherited) {}: {}", i, p_base[i]);
                        }
                        ImguiTextStdFmt("Passive 0: {} {}", cat.passive_0, cat.passive_0_sidecar);
                        ImguiTextStdFmt("Passive 1: {} {}", cat.passive_1, cat.passive_1_sidecar);
                        ImguiTextStdFmt("Mutation 0: {} {}", cat.passive_2, cat.passive_2_sidecar);
                        ImguiTextStdFmt("Mutation 1: {} {}", cat.passive_3, cat.passive_3_sidecar);
                        ImguiTextStdFmt("Equipment");
                        if(ImGui::BeginTable("equipment_table", 10)) {
                            ImGui::TableSetupColumn("Thing", ImGuiTableColumnFlags_WidthStretch, 0.5f);
                            ImGui::TableSetupColumn("ID", ImGuiTableColumnFlags_WidthStretch, 0.5f);
                            ImGui::TableSetupColumn("Name", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                            ImGui::TableSetupColumn("unknown_0", ImGuiTableColumnFlags_WidthStretch, 0.5f);
                            ImGui::TableSetupColumn("unknown_1", ImGuiTableColumnFlags_WidthStretch, 0.5f);
                            ImGui::TableSetupColumn("unknown_2", ImGuiTableColumnFlags_WidthStretch, 0.5f);
                            ImGui::TableSetupColumn("unknown_3", ImGuiTableColumnFlags_WidthStretch, 0.5f);
                            ImGui::TableSetupColumn("unknown_4", ImGuiTableColumnFlags_WidthStretch, 0.5f);
                            ImGui::TableSetupColumn("unknown_5", ImGuiTableColumnFlags_WidthStretch, 0.5f);
                            ImGui::TableSetupColumn("unknown_6", ImGuiTableColumnFlags_WidthStretch, 0.5f);
                            ImGui::TableHeadersRow();
                            Equipment *p_base = &cat.head;
                            for(uint32_t i = 0; i < 5; i++) {
                                ImGui::TableNextRow();
                                ImGui::TableNextColumn();
                                const char *label = i == 0 ? "head" :
                                                    i == 1 ? "face" :
                                                    i == 2 ? "neck" :
                                                    i == 3 ? "weapon" :
                                                    "trinket";
                                ImguiTextStdFmt("{}", label);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_base[i].id);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_base[i].name);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_base[i].unknown_0);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_base[i].unknown_1);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_base[i].unknown_2);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_base[i].unknown_3);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_base[i].unknown_4);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_base[i].unknown_5);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", p_base[i].unknown_6);
                            }
                            ImGui::EndTable();
                        }
                        ImguiTextStdFmt("Collar: {}", cat.collar);
                        ImguiTextStdFmt("Level: {}", cat.level);
                        ImguiTextStdFmt("COI: {}", cat.coi);
                        ImguiTextStdFmt("Birthday: {}", cat.birthday); // TODO calculate days ago
                        ImguiTextStdFmt("Deathday (if died in house): {}", cat.deathday_house);
                        ImguiTextStdFmt("unknown 17");
                        ImguiTextStdFmt("unknown 17 size/capacity: {} {}", cat.unknown_17.size, cat.unknown_17.capacity);
                        if(ImGui::BeginTable("unknown_17_table", 2)) {
                            ImGui::TableSetupColumn("Index", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                            ImGui::TableSetupColumn("Value", ImGuiTableColumnFlags_WidthStretch, 3.0f);
                            ImGui::TableHeadersRow();
                            for(uint32_t i = 0; i < cat.unknown_17.size; i++) {
                                ImGui::TableNextRow();
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", i);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", cat.unknown_17.ptr[i]);
                            }
                            ImGui::EndTable();
                        }
                        ImguiTextStdFmt("unknown 19: {}", cat.unknown_19);
                        ImguiTextStdFmt("unknown 20: {}", cat.unknown_20);
                        ImguiTextStdFmt("unknown 21: {}", cat.unknown_21);
                        ImguiTextStdFmt("unknown 22: {}", cat.unknown_22);
                        ImguiTextStdFmt("unknown 23: {}", cat.unknown_23);
                        ImguiTextStdFmt("Injuries");
                        if(ImGui::BeginTable("injury_table", 2)) {
                            ImGui::TableSetupColumn("Index", ImGuiTableColumnFlags_WidthStretch, 1.0f);
                            ImGui::TableSetupColumn("Count", ImGuiTableColumnFlags_WidthStretch, 3.0f);
                            ImGui::TableHeadersRow();
                            for(int i = 0; i < 16; i++) {
                                ImGui::TableNextRow();
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", i);
                                ImGui::TableNextColumn();
                                ImguiTextStdFmt("{}", cat.injuries[i]);
                            }
                            ImGui::EndTable();
                        }
                        ImGui::TreePop();
                    }
                    current = current->_Next;
                }
            }
        }
        ImGui::EndChild();
    }
    ImGui::End();
}

void deinitialize_imgui() {
    if(P.initialized) {
        ImGui_ImplOpenGL3_Shutdown();
        ImGui_ImplSDL3_Shutdown();
        ImGui::DestroyContext();
    }
}

MAKE_PHOOK("SDL_GL_SwapWindow",
    bool, __cdecl, SDL_GL_SwapWindow,
    SDL_Window *window
) {
    // multi-viewport support code will call SDL_GL_SwapWindow to paint onto other windows
    // if so, don't attempt to inject imgui again
    if(P.swapwindow_hook_nested_call_guard) {
        return SDL_GL_SwapWindow_hook.orig(window);
    }

    if(!P.initialized) {
        IMGUI_CHECKVERSION();
        ImGui::CreateContext();

        ImGuiIO& io = ImGui::GetIO();
        io.IniFilename = nullptr;
        io.LogFilename = nullptr;
        // multi-viewport works, but is glitchy with fullscreen (dragging to edge of window will cause flickering)
        // io.ConfigFlags |= ImGuiConfigFlags_ViewportsEnable;

        ImGui_ImplSDL3_InitForOpenGL(window, SDL_GL_GetCurrentContext());
        ImGui_ImplOpenGL3_Init();
        P.initialized = true;
    }

    ImGui_ImplOpenGL3_NewFrame();
    ImGui_ImplSDL3_NewFrame();
    ImGui::NewFrame();

    if(!P.hide_all) {
        show_main_menu_bar();
        if(P.show_imgui_demo) {
            ImGui::ShowDemoWindow(&P.show_imgui_demo);
        }
        show_feline_therapist_window();
        show_data_explorer_window();
        show_debug_console_window();
    }

    ImGui::Render();
    ImGui_ImplOpenGL3_RenderDrawData(ImGui::GetDrawData());

    ImGuiIO& io = ImGui::GetIO();
    if(io.ConfigFlags & ImGuiConfigFlags_ViewportsEnable) {
        SDL_GLContext backup_current_context = SDL_GL_GetCurrentContext();
        ImGui::UpdatePlatformWindows();
        P.swapwindow_hook_nested_call_guard = true;
        ImGui::RenderPlatformWindowsDefault();
        P.swapwindow_hook_nested_call_guard = false;
        SDL_GL_MakeCurrent(window, backup_current_context);
    }

    bool result = SDL_GL_SwapWindow_hook.orig(window);

    // make sure to call the original function before initiating dll eject
    // (Detours will repoint hook->orig to hook->target, but we don't want to depend on that)
    // (we want to exit immediately from the dll after starting eject)
    if(P.request_dll_eject) {
        P.request_dll_eject = false;
        initiate_dll_eject();
    }

    return result;
}

MAKE_PHOOK("SDL_PollEvent",
    bool, __cdecl, SDL_PollEvent,
    SDL_Event *event
) {
    if(P.initialized) {
        // retrieve event, let imgui take a look first
        // if imgui uses the event, fetch the next event and retry
        // return the validity indicator for the first event that imgui did not use
        ImGuiIO& io = ImGui::GetIO();
        while(SDL_PollEvent_hook.orig(event)) {
            // function returns a bool here, "I positively decoded the event"
            // but it does not tell us "I reacted to the event so it should be masked"
            ImGui_ImplSDL3_ProcessEvent(event);

            // instead imgui gives us io.WantCaptureMouse/io.WantCaptureKeyboard
            // we match the list of event types processed by the backend against those indicators
            switch (event->type) {
                case SDL_EVENT_MOUSE_MOTION:
                case SDL_EVENT_MOUSE_WHEEL:
                // imgui will internally pair click/button downs/ups and filter accordingly to prevent sticking
                case SDL_EVENT_MOUSE_BUTTON_DOWN:
                case SDL_EVENT_MOUSE_BUTTON_UP:
                    if(io.WantCaptureMouse) {
                        continue;
                    } else {
                        return true;
                    }
                    break;

                case SDL_EVENT_TEXT_INPUT:
                case SDL_EVENT_KEY_DOWN:
                case SDL_EVENT_KEY_UP:
                    if(io.WantCaptureKeyboard) {
                        continue;
                    } else {
                        // Left Alt isn't used by the game by default, use it to toggle imgui
                        if(event->type == SDL_EVENT_KEY_DOWN && event->key.key == SDLK_LALT) {
                            P.hide_all ^= true;
                        }
                        return true;
                    }
                    break;

                // sampled by backend, but likely unrelated to io.WantCaptureMouse/io.WantCaptureKeyboard
                // case SDL_EVENT_WINDOW_MOUSE_ENTER:
                // case SDL_EVENT_WINDOW_MOUSE_LEAVE:
                // case SDL_EVENT_WINDOW_FOCUS_GAINED:
                // case SDL_EVENT_WINDOW_FOCUS_LOST:
                // case SDL_EVENT_GAMEPAD_ADDED:
                // case SDL_EVENT_GAMEPAD_REMOVED:
                default:
                    return true;
                    break;
            }
        }
        // no events for the host
        return false;
    } else {
        return SDL_PollEvent_hook.orig(event);
    }
}
