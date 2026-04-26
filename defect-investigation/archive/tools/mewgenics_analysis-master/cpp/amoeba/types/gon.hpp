#pragma once

#include "types/msvc.hpp"
#include "types/phmap.hpp"

#include <vector>

// Layout description for GON objects, as implemented when compiled with MSVC 2022.
//
// Contains significant fragments of implementation written by the man himself!
// https://github.com/TylerGlaiel/GON/blob/7f9600b278231a1d458e0ca7f44784e10cffa953/gon.cpp
//
// Copyright (c) 2018 Tyler Glaiel
// MIT License
//
// polymeric 2026

// FIXME clean these later, only focused edits made to this code for now
#if defined(__GNUC__) || defined(__clang__)
static_assert(true); // makes clangd happy by ending preamble section
#pragma GCC diagnostic push
#pragma GCC diagnostic ignored "-Wsign-compare"
#endif

struct GonObject {
    struct StringHasher {
        static uint64_t hash(MsvcReleaseModeXString *key) {
            // TODO
            (void)key;
            __debugbreak();
            return 0;
        }
        static bool identical(MsvcReleaseModeXString *key1, MsvcReleaseModeXString *key2) {
            // TODO
            (void)key1;
            (void)key2;
            __debugbreak();
            return false;
        }
    };

    enum class FieldType : int {
        NULLGON,
        STRING,
        NUMBER,
        OBJECT,
        ARRAY,
        BOOL
    };

    PhmapFlatHashSap<MsvcReleaseModeXString, int, StringHasher> children_map;
    MsvcReleaseModeVector<GonObject> children_array;
    int int_data;
    double float_data;
    bool bool_data;
    MsvcReleaseModeXString string_data;
    MsvcReleaseModeXString name;
    FieldType type;

    static bool IsWhitespace(char c){
        return c==' '||c=='\n'||c=='\r'||c=='\t';
    }

    static bool IsSymbol(char c){
        return c=='='||c==','||c==':'||c=='{'||c=='}'||c=='['||c==']';
    }

    static bool IsIgnoredSymbol(char c){
        return c=='='||c==','||c==':';
    }

    static bool ends_with(const std::string& str, const std::string& suffix){
        if(str.size() < suffix.size()) return false;
        for(int i = (int)str.size()-1, j = (int)suffix.size()-1; j>=0; j--, i--){
            if(str[i] != suffix[j]) return false;
        }
        return true;
    }

    static std::vector<std::string> Tokenize(std::string data){
        std::vector<std::string> tokens;

        bool inString = false;
        bool inComment = false;
        bool escaped = false;
        std::string current_token = "";
        for(int i = 0; i<data.size(); i++){
            if(!inString && !inComment){
                if(IsSymbol(data[i])){
                    if(current_token != ""){
                        tokens.push_back(current_token);
                        current_token = "";
                    }

                    if(!IsIgnoredSymbol(data[i])){
                        current_token += data[i];
                        tokens.push_back(current_token);
                        current_token = "";
                    }
                    continue;
                }

                if(IsWhitespace(data[i])){
                    if(current_token != ""){
                        tokens.push_back(current_token);
                        current_token = "";
                    }

                    continue;
                }

                if(data[i] == '#'){
                    if(current_token != ""){
                        tokens.push_back(current_token);
                        current_token = "";
                    }

                    inComment = true;
                    continue;
                }
                if(data[i] == '"'){
                    if(current_token != ""){
                        tokens.push_back(current_token);
                        current_token = "";
                    }

                    inString = true;
                    continue;
                }

                current_token += data[i];
            }

            if(inString){
                if(escaped){
                    if(data[i] == 'n'){
                        current_token += '\n';
                    } else {
                        current_token += data[i];
                    }
                    escaped = false;
                } else if(data[i] == '\\'){
                    escaped = true;
                } else if(!escaped && data[i] == '"'){
                    tokens.push_back(current_token);
                    current_token = "";
                    inString = false;
                    continue;
                } else {
                    current_token += data[i];
                    continue;
                }
            }

            if(inComment){
                if(data[i] == '\n'){
                    inComment = false;
                    continue;
                }
            }
        }

        if(current_token != "") tokens.push_back(current_token);

        return tokens;
    }

    static std::string escaped_string(std::string input){
        auto tokenized = Tokenize(input);
        bool needs_quotes = tokenized.size() != 1 || tokenized[0] != input;

        std::string out_str;
        for(int i = 0; i<input.size(); i++){
            if(input[i] == '\n'){
                needs_quotes = true;
                out_str += "\\n";
            } else if(input[i] == '\\'){
                needs_quotes = true;
                out_str += "\\\\";
            } else if(input[i] == '\"'){
                needs_quotes = true;
                out_str += "\\\"";
            } else {
                out_str += input[i];
            }
        }

        if(needs_quotes) return "\"" + out_str + "\"";
        return out_str;
    }

    std::string SaveToStr(bool compact = false) const;
    std::string GetOutStr(const std::string& tab = "    ", const std::string& line_break = "\n", const std::string& current_tab = "") const;
};
static_assert(sizeof(GonObject) == 0xB0);

inline std::string GonObject::SaveToStr(bool compact) const {
    std::string res;
    res += escaped_string(name)+" "+GetOutStr(compact?"":"    ", compact?" ":"\n");
    /*for(int i = 0; i<children_array.size(); i++) {
        if(!res.empty()) res += (compact?" ":"\n");
        res += escaped_string(children_array[i].name)+" "+children_array[i].GetOutStr(compact?"":"    ", compact?" ":"\n");
    }*/
    return res;
}

inline std::string GonObject::GetOutStr(const std::string& tab, const std::string& line_break, const std::string& current_tab) const {
    std::string out = "";

    if(type == FieldType::OBJECT){
        out += "{"+line_break;
        for(int i = 0; i<children_array.size(); i++){
            out += current_tab+tab+escaped_string(children_array[i].name)+" "+children_array[i].GetOutStr(tab, line_break, tab+current_tab);
            if(!ends_with(out, line_break)) out += line_break;
        }
        out += current_tab+"}"+line_break;
    }

    if(type == FieldType::ARRAY){
        bool short_array = true;
        size_t strlengthtotal = 0;
        for(int i = 0; i<children_array.size(); i++){
            if(children_array[i].type == GonObject::FieldType::ARRAY)
                short_array = false;

            if(children_array[i].type == GonObject::FieldType::OBJECT)
                short_array = false;

            if(children_array[i].type == GonObject::FieldType::STRING)
                strlengthtotal += children_array[i].string_data._Mysize;


            if(!short_array) break;
        }
        if(strlengthtotal > 80) short_array = false;

        if(short_array){
            out += "[";
            for(int i = 0; i<children_array.size(); i++){
                out += children_array[i].GetOutStr(tab, line_break, tab+current_tab);
                if(i != children_array.size()-1) out += " ";
            }
            out += "]"+line_break;
        } else {
            out += "["+line_break;
            for(int i = 0; i<children_array.size(); i++){
                out += current_tab+tab+children_array[i].GetOutStr(tab, line_break, tab+current_tab);
                if(!ends_with(out, line_break)) out += line_break;
            }
            out += current_tab+"]"+line_break;
        }
    }

    if(type == FieldType::STRING){
        out += escaped_string(string_data);
    }

    if(type == FieldType::NUMBER){
        out += std::to_string(int_data);
    }

    if(type == FieldType::BOOL){
        if(bool_data){
            out += "true";
        } else {
            out += "false";
        }
    }

    if(type == FieldType::NULLGON){
        out += "null";
    }

    return out;
}

#if defined(__GNUC__) || defined(__clang__)
#pragma GCC diagnostic pop
#endif
