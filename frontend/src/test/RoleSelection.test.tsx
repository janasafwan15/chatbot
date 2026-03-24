// src/test/RoleSelection.test.tsx
import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { RoleSelection } from "../pages/RoleSelection";

// framer-motion mock — نتجنب مشاكل الـ animation في الـ tests
vi.mock("framer-motion", () => {
  const clean = ({ children, whileHover, whileTap, initial, animate, transition, ...p }: any) => p;
  return {
    motion: {
      div:    (props: any) => <div {...clean(props)}>{props.children}</div>,
      button: (props: any) => <button {...clean(props)}>{props.children}</button>,
    },
  };
});

describe("RoleSelection", () => {
  it("يعرض زر المواطن وزر الموظف", () => {
    render(<RoleSelection onSelectRole={vi.fn()} />);
    expect(screen.getByText("مواطن")).toBeInTheDocument();
    expect(screen.getByText("موظف / مدير")).toBeInTheDocument();
  });

  it("زر المواطن يستدعي onSelectRole بـ citizen", () => {
    const handler = vi.fn();
    render(<RoleSelection onSelectRole={handler} />);
    fireEvent.click(screen.getByText("مواطن"));
    expect(handler).toHaveBeenCalledWith("citizen");
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("زر الموظف يستدعي onSelectRole بـ employee", () => {
    const handler = vi.fn();
    render(<RoleSelection onSelectRole={handler} />);
    fireEvent.click(screen.getByText("موظف / مدير"));
    expect(handler).toHaveBeenCalledWith("employee");
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("يعرض عنوان النظام", () => {
    render(<RoleSelection onSelectRole={vi.fn()} />);
    expect(screen.getByText("نظام الدعم الذكي")).toBeInTheDocument();
  });
});

