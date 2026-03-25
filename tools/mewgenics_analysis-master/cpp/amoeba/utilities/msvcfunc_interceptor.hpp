#pragma once

#include "types/msvc.hpp"

#include <functional>

// This wrapper implements a MsvcFuncNoAlloc that mirrors the calling interface of another MsvcFuncNoAlloc.
// It stores a pointer to this "wrapped" MsvcFuncNoAlloc in its capture environment.
// The user provides a native std::function to "intercept" calls that target the "wrapped" MsvcFuncNoAlloc.
// When the wrapper is invoked, it calls the native std::function.
// The native std::function is given the "wrapped" MsvcFuncNoAlloc and is free to execute any code.
// The wrapper will forward destruction to the "wrapped" MsvcFuncNoAlloc.
//
// polymeric 2026

// The _Callable layout for the wrapper
// Captures a native std::function and a pointer to a MsvcFuncNoAlloc
template <class _Callable, class _Rx, class... _Types>
struct CallableWrapped;
template <class _Callable, class _Rx, class... _Types>
struct CallableWrapped<_Callable, _Rx(_Types...)> {
    using Wrapped = MsvcFuncNoAlloc<_Callable, _Rx(_Types...)>;
    using Wrapper = MsvcFuncNoAlloc<CallableWrapped, _Rx(_Types...)>;
    std::function<_Rx(Wrapper* thiss, _Types*... _Args)> *interceptor;
    Wrapped *wrapped;
};

// CallableWrapped is small and constant sized (1 qword for interceptor + 1 qword for wrapped)
template <class _Callable, class _Rx, class... _Types>
struct MsvcFuncNoAllocWrapper;
template <class _Callable, class _Rx, class... _Types>
struct MsvcFuncNoAllocWrapper<_Callable, _Rx(_Types...)> :
    MsvcFuncNoAlloc<CallableWrapped<_Callable, _Rx(_Types...)>, _Rx(_Types...)>
{
    // these template expansions are pretty horrifying
    using WrapperCallable = CallableWrapped<_Callable, _Rx(_Types...)>;
    using Wrapper = MsvcFuncNoAlloc<WrapperCallable, _Rx(_Types...)>;
    using WrapperVTable = MsvcFuncNoAlloc_vtable<WrapperCallable, _Rx(_Types...)>;
    using Wrapped = MsvcFuncNoAlloc<_Callable, _Rx(_Types...)>;

    static Wrapper* _Copy(Wrapper const* thiss, void* _Where) {
        Wrapper *dest = reinterpret_cast<MsvcFuncNoAllocWrapper *>(_Where);
        dest->vtable = thiss->vtable;
        // _Callee is just 2 pointers, copying is trivial
        dest->_Mystorage._Callee = thiss->_Mystorage._Callee;
        // TODO Need to implement reference counting if this wrapper is ever copied,
        // in order to know when to invoke _Delete_this on the wrapped function
        // We block MsvcFuncNoAllocWrapper from being copied while handled in our program,
        // but it can be copied in the host program
        __debugbreak();
        return dest;
    }
    static Wrapper* _Move(Wrapper* thiss, void* _Where) {
        // oddly enough, _Move degenerates to a constant zero return
        // not sure why, but information comes from decompilation
        // TODO If a wrapped function is ever moved, worth taking a look
        (void)thiss;
        (void)_Where;
        __debugbreak();
        return nullptr;
    }
    static _Rx _Do_call(Wrapper* thiss, _Types*... _Args) {
        // redirect control to a user-provided interceptor stored in the capture body
        return (*thiss->_Mystorage._Callee.interceptor)(thiss , _Args...);
    }
    static const MsvcTypeInfo* _Target_type(Wrapper const* thiss) {
        // redirect this call to wrapped instance
        return thiss->_Mystorage._Callee.wrapped->vtable->_Target_type(thiss->_Mystorage._Callee.wrapped);
    }
    static void _Delete_this(Wrapper* thiss, bool _Dealloc) {
        // since we are always small, _Dealloc will never be true (outer destructor checks _Ptrs[6] == this)
        // we never would've been allocated in a fashion that requires us to perform any deletes
        (void)thiss;
        (void)_Dealloc;
        // forward destruction to the wrapped instance, which we consumed and need to terminate;
        // this is the destructor implementation that our owner is currently executing against us
        // if this wrapper is ever copied, probably need to use a refcount to ensure this is only called once
        auto wrapped = thiss->_Mystorage._Callee.wrapped;
        if(wrapped->_Mystorage._Ptrs[6] != nullptr) {
            bool is_large = wrapped->_Mystorage._Ptrs[6] != wrapped;
            wrapped->vtable->_Delete_this(wrapped, is_large);
            wrapped->_Mystorage._Ptrs[6] = nullptr;
        }
    }
    static const void* _Get(Wrapper const* thiss) {
        // redirect this call to wrapped instance
        return thiss->_Mystorage._Callee.wrapped->vtable->_Get(thiss->_Mystorage._Callee.wrapped);
    }

    static _Rx invoke_orig(Wrapper* thiss, _Types*... _Args) {
        return thiss->_Mystorage._Callee.wrapped->vtable->_Do_call(thiss->_Mystorage._Callee.wrapped, _Args...);
    }

    inline static WrapperVTable my_vtable = {
        _Copy, _Move, _Do_call, _Target_type, _Delete_this, _Get
    };

    MsvcFuncNoAllocWrapper(Wrapped *wrapped, std::function<_Rx(Wrapper* thiss, _Types*... _Args)> *interceptor) :
        Wrapper(&my_vtable, WrapperCallable { interceptor, wrapped })
    {
        // point to start of this object to mark it as small-storage
        this->_Mystorage._Ptrs[6] = reinterpret_cast<void *>(this);
    }

    // TODO MsvcFuncNoAllocWrapper<...> should be a trivial alias of MsvcFuncNoAlloc<CallableWrapped<...>, ...>,
    // should somehow eliminate this reinterpret_cast
    Wrapped *as_target_type() {
        return reinterpret_cast<Wrapped *>(this);
    }
};
